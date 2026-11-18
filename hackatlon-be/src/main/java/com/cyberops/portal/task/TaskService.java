package com.cyberops.portal.task;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cyberops.portal.auth.CurrentUser;
import com.cyberops.portal.common.ForbiddenException;
import com.cyberops.portal.common.NotFoundException;
import com.cyberops.portal.notification.NotificationRepository;
import com.cyberops.portal.task.TaskDtos.HistoryEntry;
import com.cyberops.portal.task.TaskDtos.TaskCreate;
import com.cyberops.portal.task.TaskDtos.TaskDetail;
import com.cyberops.portal.task.TaskDtos.TaskSummary;
import com.cyberops.portal.task.TaskRepository.TaskRow;

@Service
public class TaskService {

	public static final String DEFAULT_ORDER = TaskRepository.SEVERITY_ORDER + ", t.modified_date DESC, t.id DESC";

	private final TaskRepository repo;
	private final NotificationRepository notifications;

	public TaskService(TaskRepository repo, NotificationRepository notifications) {
		this.repo = repo;
		this.notifications = notifications;
	}

	// ---------------------------------------------------------------- read

	public List<TaskSummary> list(CurrentUser me, String status, String severity, String q, Long assigneeId,
			Boolean overdue) {
		MapSqlParameterSource p = new MapSqlParameterSource();
		StringBuilder where = new StringBuilder(TaskVisibility.where(me, p));
		if (status != null && !status.isBlank()) {
			where.append(" AND t.task_status = :status");
			p.addValue("status", status.trim().toUpperCase());
		}
		if (severity != null && !severity.isBlank()) {
			where.append(" AND t.task_severity = :severity");
			p.addValue("severity", severity.trim().toUpperCase());
		}
		if (q != null && !q.isBlank()) {
			where.append(" AND (t.task_title ILIKE :q OR t.task_description ILIKE :q"
					+ " OR printf('TSK-%04d', t.id) ILIKE :q)");
			p.addValue("q", "%" + q.trim() + "%");
		}
		if (assigneeId != null) {
			where.append(" AND EXISTS (SELECT 1 FROM task_assignee fa WHERE fa.task_id = t.id AND fa.user_id = :fAssignee)");
			p.addValue("fAssignee", assigneeId);
		}
		if (Boolean.TRUE.equals(overdue)) {
			where.append(" AND t.due_date < :now AND t.task_status <> 'DONE'");
			p.addValue("now", TimeUtil.ts(TimeUtil.now()));
		}
		return summaries(repo.find(where.toString(), p, DEFAULT_ORDER, null));
	}

	/** Builds summaries for rows, loading assignees in one query. */
	public List<TaskSummary> summaries(List<TaskRow> rows) {
		Map<Long, List<UserRef>> a = repo.assignees(rows.stream().map(TaskRow::id).toList());
		LocalDateTime now = TimeUtil.now();
		return rows.stream().map(r -> summary(r, a.getOrDefault(r.id(), List.of()), now)).toList();
	}

	private static TaskSummary summary(TaskRow r, List<UserRef> assignees, LocalDateTime now) {
		return new TaskSummary(r.id(), TaskDtos.code(r.id()), r.title(), r.status(), r.severity(), assignees,
				r.backupAssignee(), TimeUtil.offset(r.dueDate()), overdue(r, now), r.handover(),
				TimeUtil.offset(r.modifiedDate()));
	}

	private static boolean overdue(TaskRow r, LocalDateTime now) {
		return r.dueDate() != null && r.dueDate().isBefore(now) && !"DONE".equals(r.status());
	}

	public TaskDetail get(CurrentUser me, long id) {
		TaskRow r = visibleRow(me, id);
		return detail(me, r);
	}

	public List<HistoryEntry> history(CurrentUser me, long id) {
		visibleRow(me, id);
		return repo.history(id);
	}

	public List<UserRef> activeUsers() {
		return repo.activeUsers();
	}

	private TaskRow visibleRow(CurrentUser me, long id) {
		MapSqlParameterSource p = new MapSqlParameterSource("id", id);
		String where = "t.id = :id AND " + TaskVisibility.where(me, p);
		List<TaskRow> rows = repo.find(where, p, "t.id", null);
		if (rows.isEmpty()) {
			throw new NotFoundException("Task bulunamadı.");
		}
		return rows.get(0);
	}

	private TaskDetail detail(CurrentUser me, TaskRow r) {
		List<UserRef> assignees = repo.assignees(List.of(r.id())).getOrDefault(r.id(), List.of());
		boolean canEdit = canEdit(me, r);
		boolean canStatus = canEdit || Objects.equals(r.backupAssigneeId(), me.id())
				|| assignees.stream().anyMatch(u -> u.id() == me.id());
		LocalDateTime now = TimeUtil.now();
		return new TaskDetail(r.id(), TaskDtos.code(r.id()), r.title(), r.status(), r.severity(), assignees,
				r.backupAssignee(), TimeUtil.offset(r.dueDate()), overdue(r, now), r.handover(),
				TimeUtil.offset(r.modifiedDate()), r.description() == null ? "" : r.description(), r.createdBy(),
				TimeUtil.offset(r.createDate()), r.modifiedBy(), canEdit, canStatus, repo.history(r.id()));
	}

	private static boolean canEdit(CurrentUser me, TaskRow r) {
		return TaskVisibility.seesAll(me) || Objects.equals(r.createdById(), me.id());
	}

	// ---------------------------------------------------------------- write

	@Transactional
	public TaskDetail create(CurrentUser me, TaskCreate req) {
		String title = requireTitle(req.title());
		String severity = enumOr(req.severity(), TaskDtos.SEVERITIES, "MEDIUM", "severity");
		String status = enumOr(req.status(), TaskDtos.STATUSES, "OPEN", "status");
		List<Long> assigneeIds = distinct(req.assigneeIds());
		if (assigneeIds.isEmpty()) {
			throw new IllegalArgumentException("assigneeIds: en az bir sorumlu seçilmelidir.");
		}
		if (!TaskVisibility.seesAll(me) && !(assigneeIds.size() == 1 && assigneeIds.get(0) == me.id())) {
			throw new ForbiddenException("Task yönetimi yetkiniz olmadan yalnızca kendinize task atayabilirsiniz.");
		}
		Map<Long, UserRef> users = resolveUsers(assigneeIds, req.backupAssigneeId());
		LocalDateTime now = TimeUtil.now();
		LocalDateTime due = TimeUtil.parse(req.dueDate());
		if (due == null) {
			due = now.plusDays(slaDays(severity));
		}
		String description = req.description() == null ? "" : req.description();
		long id = repo.insert(title, description, status, severity, due, req.backupAssigneeId(), me.id(), now);
		for (Long uid : assigneeIds) {
			repo.addAssignee(id, uid);
		}
		repo.addHistory(id, "created",
				"Task oluşturuldu. Atananlar: " + names(assigneeIds.stream().map(users::get).toList()), me.id(), now);

		Set<Long> notify = new LinkedHashSet<>(assigneeIds);
		if (req.backupAssigneeId() != null) {
			notify.add(req.backupAssigneeId());
		}
		notifyAssigned(me, id, notify, now);
		return get(me, id);
	}

	@Transactional
	public TaskDetail update(CurrentUser me, long id, Map<String, Object> body) {
		TaskRow r = visibleRow(me, id);
		if (!canEdit(me, r)) {
			throw new ForbiddenException("Bu task'ı düzenleme yetkiniz yok.");
		}
		LocalDateTime now = TimeUtil.now();
		List<String[]> logs = new ArrayList<>();

		String status = r.status();
		if (body.containsKey("status")) {
			String s = enumOr(str(body.get("status")), TaskDtos.STATUSES, r.status(), "status");
			if (!s.equals(r.status())) {
				logs.add(new String[] { "status_change",
						"Durum: " + TaskDtos.statusLabel(r.status()) + " → " + TaskDtos.statusLabel(s) });
				status = s;
			}
		}
		String severity = r.severity();
		if (body.containsKey("severity")) {
			String s = enumOr(str(body.get("severity")), TaskDtos.SEVERITIES, r.severity(), "severity");
			if (!s.equals(r.severity())) {
				logs.add(new String[] { "severity_change",
						"Önem: " + TaskDtos.severityLabel(r.severity()) + " → " + TaskDtos.severityLabel(s) });
				severity = s;
			}
		}
		String title = r.title();
		if (body.containsKey("title")) {
			String t = requireTitle(str(body.get("title")));
			if (!t.equals(r.title())) {
				logs.add(new String[] { "description_change", "Başlık: \"" + r.title() + "\" → \"" + t + "\"" });
				title = t;
			}
		}
		String description = r.description() == null ? "" : r.description();
		if (body.containsKey("description")) {
			String d = body.get("description") == null ? "" : str(body.get("description"));
			if (!d.equals(description)) {
				logs.add(new String[] { "description_change", "Açıklama güncellendi." });
				description = d;
			}
		}
		LocalDateTime due = r.dueDate();
		if (body.containsKey("dueDate")) {
			LocalDateTime d = TimeUtil.parse(body.get("dueDate"));
			if (d == null) {
				d = (r.createDate() == null ? now : r.createDate()).plusDays(slaDays(severity));
			}
			if (!Objects.equals(d, r.dueDate())) {
				logs.add(new String[] { "due_date_change",
						"Son tarih: " + TimeUtil.tr(r.dueDate()) + " → " + TimeUtil.tr(d) });
				due = d;
			}
		}

		Set<Long> notify = new LinkedHashSet<>();
		List<Long> added = List.of();
		List<Long> removed = List.of();
		if (body.containsKey("assigneeIds")) {
			List<Long> newIds = distinct(toLongList(body.get("assigneeIds")));
			if (newIds.isEmpty()) {
				throw new IllegalArgumentException("assigneeIds: en az bir sorumlu seçilmelidir.");
			}
			Set<Long> oldIds = repo.assignees(List.of(id)).getOrDefault(id, List.of()).stream().map(UserRef::id)
					.collect(Collectors.toSet());
			if (!oldIds.equals(Set.copyOf(newIds))) {
				if (!TaskVisibility.seesAll(me) && !(newIds.size() == 1 && newIds.get(0) == me.id())) {
					throw new ForbiddenException(
							"Task yönetimi yetkiniz olmadan yalnızca kendinize task atayabilirsiniz.");
				}
				added = newIds.stream().filter(u -> !oldIds.contains(u)).toList();
				removed = oldIds.stream().filter(u -> !newIds.contains(u)).toList();
				Map<Long, UserRef> users = resolveUsers(added, null);
				List<String> parts = new ArrayList<>();
				if (!added.isEmpty()) {
					parts.add("Eklenen: " + names(added.stream().map(users::get).toList()));
				}
				if (!removed.isEmpty()) {
					parts.add("Çıkarılan: " + names(removed.stream().map(repo::user).toList()));
				}
				logs.add(new String[] { "assignment_change", String.join(" | ", parts) });
				notify.addAll(added);
			}
		}
		Long backup = r.backupAssigneeId();
		if (body.containsKey("backupAssigneeId")) {
			Object raw = body.get("backupAssigneeId");
			Long b = raw == null ? null : toLong(raw);
			if (!Objects.equals(b, r.backupAssigneeId())) {
				UserRef nb = null;
				if (b != null) {
					nb = resolveUsers(List.of(), b).get(b);
				}
				logs.add(new String[] { "assignment_change", "Yedek sorumlu: "
						+ (r.backupAssignee() == null ? "—" : r.backupAssignee().displayName()) + " → "
						+ (nb == null ? "—" : nb.displayName()) });
				backup = b;
				if (b != null) {
					notify.add(b);
				}
			}
		}

		if (logs.isEmpty()) {
			return detail(me, r);
		}
		repo.update(id, title, description, status, severity, due, backup, me.id(), now);
		for (Long u : removed) {
			repo.removeAssignee(id, u);
		}
		for (Long u : added) {
			repo.addAssignee(id, u);
		}
		for (String[] l : logs) {
			repo.addHistory(id, l[0], l[1], me.id(), now);
		}
		notifyAssigned(me, id, notify, now);
		return get(me, id);
	}

	@Transactional
	public TaskDetail changeStatus(CurrentUser me, long id, String newStatus) {
		TaskRow r = visibleRow(me, id);
		TaskDetail d = detail(me, r);
		if (!d.canChangeStatus()) {
			throw new ForbiddenException("Bu task'ın durumunu değiştirme yetkiniz yok.");
		}
		if (newStatus == null || newStatus.isBlank()) {
			throw new IllegalArgumentException("status: zorunlu alan.");
		}
		String s = enumOr(newStatus, TaskDtos.STATUSES, null, "status");
		if (s.equals(r.status())) {
			return d;
		}
		LocalDateTime now = TimeUtil.now();
		repo.update(id, r.title(), r.description(), s, r.severity(), r.dueDate(), r.backupAssigneeId(), me.id(), now);
		repo.addHistory(id, "status_change",
				"Durum: " + TaskDtos.statusLabel(r.status()) + " → " + TaskDtos.statusLabel(s), me.id(), now);
		return get(me, id);
	}

	// ---------------------------------------------------------------- helpers

	private void notifyAssigned(CurrentUser me, long taskId, Collection<Long> userIds, LocalDateTime now) {
		UserRef actor = repo.user(me.id());
		String actorName = actor == null ? me.username() : actor.displayName();
		String msg = actorName + " size " + TaskDtos.code(taskId) + " işini atadı";
		for (Long u : userIds) {
			if (u != null && u != me.id()) {
				notifications.insert(u, taskId, msg, now);
			}
		}
	}

	private Map<Long, UserRef> resolveUsers(List<Long> ids, Long backupId) {
		Set<Long> all = new LinkedHashSet<>(ids);
		if (backupId != null) {
			all.add(backupId);
		}
		Map<Long, UserRef> found = repo.activeUsersByIds(all);
		for (Long id : all) {
			if (!found.containsKey(id)) {
				throw new IllegalArgumentException("Kullanıcı bulunamadı veya pasif: " + id);
			}
		}
		return found;
	}

	static int slaDays(String severity) {
		return switch (severity) {
			case "CRITICAL" -> 1;
			case "HIGH" -> 3;
			case "LOW" -> 14;
			default -> 7;
		};
	}

	private static String names(List<UserRef> users) {
		String s = users.stream().filter(Objects::nonNull).map(UserRef::displayName).sorted()
				.collect(Collectors.joining(", "));
		return s.isEmpty() ? "—" : s;
	}

	private static String requireTitle(String title) {
		if (title == null || title.isBlank()) {
			throw new IllegalArgumentException("title: zorunlu alan.");
		}
		return title.trim();
	}

	private static String enumOr(String value, List<String> allowed, String def, String field) {
		if (value == null || value.isBlank()) {
			if (def == null) {
				throw new IllegalArgumentException(field + ": zorunlu alan.");
			}
			return def;
		}
		String v = value.trim().toUpperCase();
		if (!allowed.contains(v)) {
			throw new IllegalArgumentException(field + ": geçersiz değer (" + value + ").");
		}
		return v;
	}

	private static String str(Object o) {
		return o == null ? null : o.toString();
	}

	private static List<Long> distinct(List<Long> ids) {
		if (ids == null) {
			return List.of();
		}
		return ids.stream().filter(Objects::nonNull).distinct().toList();
	}

	private static Long toLong(Object o) {
		if (o instanceof Number n) {
			return n.longValue();
		}
		try {
			return Long.parseLong(o.toString().trim());
		}
		catch (NumberFormatException e) {
			throw new IllegalArgumentException("Geçersiz id: " + o);
		}
	}

	private static List<Long> toLongList(Object o) {
		if (o == null) {
			return List.of();
		}
		if (!(o instanceof Collection<?> c)) {
			throw new IllegalArgumentException("assigneeIds: dizi olmalıdır.");
		}
		return c.stream().map(TaskService::toLong).toList();
	}
}

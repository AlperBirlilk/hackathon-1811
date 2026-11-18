package com.cyberops.portal.user;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

import com.cyberops.portal.user.UserDtos.Skill;

/** Read/write access for profiles, skills, team membership and permissions. */
@Repository
public class UserProfileRepository {

	/** Raw profile row (never contains secrets such as ldap_dn). */
	public record ProfileRow(long id, String username, String firstName, String lastName, String displayName,
			String email, String title, String department, String phone, String location, String bio, Long managerId,
			boolean isOnLeave, boolean isActive) {
	}

	public record MemberRow(PersonRef user, String title, boolean isOnLeave, long openCount, long progressCount,
			long doneCount, long overdueCount) {
	}

	public record PermissionType(long id, String code, String name) {
	}

	private final NamedParameterJdbcTemplate jdbc;

	public UserProfileRepository(NamedParameterJdbcTemplate jdbc) {
		this.jdbc = jdbc;
	}

	public Optional<ProfileRow> findProfile(long id) {
		return jdbc.query("""
				SELECT u.id, u.username, u.first_name, u.last_name, %s AS display_name, u.email, u.title,
				       u.department, u.phone, u.location, u.bio, u.manager_id, u.is_on_leave, u.is_active
				FROM app_user u WHERE u.id = :id""".formatted(PersonRef.displayNameSql("u")), Map.of("id", id),
				(rs, i) -> {
					long mgr = rs.getLong("manager_id");
					Long managerId = rs.wasNull() ? null : mgr;
					return new ProfileRow(rs.getLong("id"), rs.getString("username"), nz(rs.getString("first_name")),
							nz(rs.getString("last_name")), rs.getString("display_name"), nz(rs.getString("email")),
							nz(rs.getString("title")), nz(rs.getString("department")), nz(rs.getString("phone")),
							nz(rs.getString("location")), nz(rs.getString("bio")), managerId,
							rs.getBoolean("is_on_leave"), rs.getBoolean("is_active"));
				}).stream().findFirst();
	}

	public Optional<PersonRef> findRef(long id) {
		return jdbc.query("SELECT u.id, u.username, %s AS display_name FROM app_user u WHERE u.id = :id"
				.formatted(PersonRef.displayNameSql("u")), Map.of("id", id), UserProfileRepository::mapRef)
				.stream().findFirst();
	}

	public void updateProfile(long id, UserDtos.ProfileUpdate u) {
		// Column names are fixed literals; only values are bound as parameters.
		MapSqlParameterSource p = new MapSqlParameterSource("id", id);
		java.util.List<String> sets = new java.util.ArrayList<>();
		addSet(sets, p, "first_name", u.firstName());
		addSet(sets, p, "last_name", u.lastName());
		addSet(sets, p, "title", u.title());
		addSet(sets, p, "department", u.department());
		addSet(sets, p, "location", u.location());
		addSet(sets, p, "email", u.email());
		addSet(sets, p, "phone", u.phone());
		addSet(sets, p, "bio", u.bio());
		addSet(sets, p, "is_on_leave", u.isOnLeave());
		if (sets.isEmpty()) {
			return;
		}
		jdbc.update("UPDATE app_user SET " + String.join(", ", sets) + " WHERE id = :id", p);
	}

	private static void addSet(java.util.List<String> sets, MapSqlParameterSource p, String column, Object value) {
		if (value != null) {
			sets.add(column + " = :" + column);
			p.addValue(column, value instanceof String str ? str.trim() : value);
		}
	}

	// ---- skills ----

	public List<Skill> skills(long userId) {
		return jdbc.query("""
				SELECT id, skill_name, kind, create_date FROM user_skill
				WHERE user_id = :u ORDER BY kind, skill_name""", Map.of("u", userId), UserProfileRepository::mapSkill);
	}

	public Skill insertSkill(long userId, String name, String kind) {
		long id = jdbc.queryForObject(
				"INSERT INTO user_skill (user_id, skill_name, kind) VALUES (:u, :n, :k) RETURNING id",
				new MapSqlParameterSource("u", userId).addValue("n", name).addValue("k", kind), Long.class);
		return jdbc.query("SELECT id, skill_name, kind, create_date FROM user_skill WHERE id = :id",
				Map.of("id", id), UserProfileRepository::mapSkill).get(0);
	}

	/** Deletes the skill only if owned by the user; returns affected row count. */
	public int deleteSkill(long userId, long skillId) {
		return jdbc.update("DELETE FROM user_skill WHERE id = :id AND user_id = :u",
				Map.of("id", skillId, "u", userId));
	}

	// ---- team ----

	/** Team members with task counts; managerId null = all active users except excludeId. */
	public List<MemberRow> members(Long managerId, long excludeId) {
		MapSqlParameterSource p = new MapSqlParameterSource("ex", excludeId);
		String mgrFilter = "";
		if (managerId != null) {
			p.addValue("mgr", managerId);
			mgrFilter = " AND u.manager_id = :mgr";
		}
		String sql = """
				SELECT u.id, u.username, %s AS display_name, u.title, u.is_on_leave,
				  (SELECT count(*) FROM task t JOIN task_assignee ta ON ta.task_id = t.id
				     WHERE ta.user_id = u.id AND t.task_status = 'OPEN') AS open_count,
				  (SELECT count(*) FROM task t JOIN task_assignee ta ON ta.task_id = t.id
				     WHERE ta.user_id = u.id AND t.task_status = 'IN_PROGRESS') AS progress_count,
				  (SELECT count(*) FROM task t JOIN task_assignee ta ON ta.task_id = t.id
				     WHERE ta.user_id = u.id AND t.task_status = 'DONE') AS done_count,
				  (SELECT count(*) FROM task t JOIN task_assignee ta ON ta.task_id = t.id
				     WHERE ta.user_id = u.id AND t.task_status <> 'DONE'
				       AND t.due_date IS NOT NULL AND t.due_date < current_localtimestamp()) AS overdue_count
				FROM app_user u
				WHERE u.is_active AND u.id <> :ex %s
				ORDER BY display_name""".formatted(PersonRef.displayNameSql("u"), mgrFilter);
		return jdbc.query(sql, p, (rs, i) -> new MemberRow(mapRef(rs, i), nz(rs.getString("title")),
				rs.getBoolean("is_on_leave"), rs.getLong("open_count"), rs.getLong("progress_count"),
				rs.getLong("done_count"), rs.getLong("overdue_count")));
	}

	public List<PersonRef> candidates(long excludeId) {
		return jdbc.query("""
				SELECT u.id, u.username, %s AS display_name FROM app_user u
				WHERE u.is_active AND u.manager_id IS NULL AND u.id <> :ex
				ORDER BY display_name""".formatted(PersonRef.displayNameSql("u")), Map.of("ex", excludeId),
				UserProfileRepository::mapRef);
	}

	public int setManagerIfNone(long userId, long managerId) {
		return jdbc.update("UPDATE app_user SET manager_id = :m WHERE id = :id AND manager_id IS NULL AND is_active",
				Map.of("m", managerId, "id", userId));
	}

	public int clearManager(long userId) {
		return jdbc.update("UPDATE app_user SET manager_id = NULL WHERE id = :id", Map.of("id", userId));
	}

	// ---- permissions ----

	public List<PermissionType> permissionTypes() {
		return jdbc.query("SELECT id, code, permission_name FROM permission_type ORDER BY id", Map.of(),
				(rs, i) -> new PermissionType(rs.getLong("id"), rs.getString("code"), rs.getString("permission_name")));
	}

	public List<String> permissionCodes(long userId) {
		return jdbc.queryForList("""
				SELECT pt.code FROM user_permission up JOIN permission_type pt ON pt.id = up.permission_type_id
				WHERE up.user_id = :id ORDER BY pt.id""", Map.of("id", userId), String.class);
	}

	public void grant(long userId, long permissionTypeId, long grantedBy) {
		jdbc.update("""
				INSERT OR IGNORE INTO user_permission (user_id, permission_type_id, granted_by, granted_date)
				VALUES (:u, :p, :g, current_localtimestamp())""",
				Map.of("u", userId, "p", permissionTypeId, "g", grantedBy));
	}

	public void revoke(long userId, long permissionTypeId) {
		jdbc.update("DELETE FROM user_permission WHERE user_id = :u AND permission_type_id = :p",
				Map.of("u", userId, "p", permissionTypeId));
	}

	// ---- mappers ----

	static PersonRef mapRef(ResultSet rs, int i) throws SQLException {
		return new PersonRef(rs.getLong("id"), rs.getString("username"), rs.getString("display_name"));
	}

	private static Skill mapSkill(ResultSet rs, int i) throws SQLException {
		return new Skill(rs.getLong("id"), rs.getString("skill_name"), rs.getString("kind"),
				toOffset(rs.getTimestamp("create_date")));
	}

	public static OffsetDateTime toOffset(Timestamp ts) {
		return ts == null ? null : ts.toLocalDateTime().atZone(ZoneId.systemDefault()).toOffsetDateTime();
	}

	private static String nz(String s) {
		return s == null ? "" : s;
	}
}

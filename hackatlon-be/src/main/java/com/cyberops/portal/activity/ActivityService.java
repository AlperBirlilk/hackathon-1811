package com.cyberops.portal.activity;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cyberops.portal.activity.ActivityDtos.ActivityCreate;
import com.cyberops.portal.activity.ActivityDtos.ActivitySummary;
import com.cyberops.portal.auth.CurrentUser;
import com.cyberops.portal.common.ForbiddenException;
import com.cyberops.portal.common.NotFoundException;
import com.cyberops.portal.common.PermissionCodes;

@Service
public class ActivityService {

	private static final Set<String> TYPES = Set.of("TRAINING", "CONFERENCE", "OTHER");
	private static final Set<String> PARTICIPATION = Set.of("INDIVIDUAL", "CORPORATE");
	private static final Set<String> SCOPES = Set.of("upcoming", "past", "mine");

	private final ActivityRepository repo;

	public ActivityService(ActivityRepository repo) {
		this.repo = repo;
	}

	public List<ActivitySummary> list(CurrentUser me, String scope) {
		String s = scope == null || scope.isBlank() ? "upcoming" : scope.trim().toLowerCase();
		if (!SCOPES.contains(s)) {
			throw new IllegalArgumentException("Geçersiz scope: " + scope);
		}
		return repo.list(s, me.id());
	}

	@Transactional
	public ActivitySummary create(CurrentUser me, ActivityCreate req) {
		if (!me.hasPerm(PermissionCodes.ACTIVITY_MANAGEMENT)) {
			throw new ForbiddenException();
		}
		String type = enumOr(req.type(), "OTHER", TYPES, "etkinlik türü");
		String part = enumOr(req.participationType(), "INDIVIDUAL", PARTICIPATION, "katılım türü");
		if (req.contactPersonId() != null && !repo.userExists(req.contactPersonId())) {
			throw new IllegalArgumentException("İletişim kişisi bulunamadı: " + req.contactPersonId());
		}
		Set<Long> attendeeIds = new LinkedHashSet<>(req.attendeeIds() == null ? List.of() : req.attendeeIds());
		for (Long uid : attendeeIds) {
			if (uid == null || !repo.userExists(uid)) {
				throw new IllegalArgumentException("Katılımcı bulunamadı: " + uid);
			}
		}
		long id = repo.insert(req.name().trim(), req.description() == null ? "" : req.description(),
				parseDate(req.date()), req.location() == null ? "" : req.location(), type, part,
				req.contactPersonId(), me.id());
		attendeeIds.forEach(uid -> repo.addAttendee(id, uid));
		return repo.find(id, me.id()).orElseThrow();
	}

	@Transactional
	public boolean toggleJoin(CurrentUser me, long activityId) {
		if (!repo.exists(activityId)) {
			throw new NotFoundException("Etkinlik bulunamadı.");
		}
		if (repo.removeAttendee(activityId, me.id()) > 0) {
			return false;
		}
		repo.addAttendee(activityId, me.id());
		return true;
	}

	private static String enumOr(String value, String def, Set<String> allowed, String label) {
		if (value == null || value.isBlank()) {
			return def;
		}
		String v = value.trim().toUpperCase();
		if (!allowed.contains(v)) {
			throw new IllegalArgumentException("Geçersiz " + label + ": " + value);
		}
		return v;
	}

	static LocalDateTime parseDate(String s) {
		try {
			return OffsetDateTime.parse(s).atZoneSameInstant(ZoneId.systemDefault()).toLocalDateTime();
		}
		catch (DateTimeParseException e) {
			try {
				return LocalDateTime.parse(s);
			}
			catch (DateTimeParseException e2) {
				try {
					return java.time.LocalDate.parse(s).atStartOfDay();
				}
				catch (DateTimeParseException e3) {
					throw new IllegalArgumentException("Geçersiz tarih: " + s);
				}
			}
		}
	}
}

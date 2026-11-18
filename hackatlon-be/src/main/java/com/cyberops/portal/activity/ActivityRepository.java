package com.cyberops.portal.activity;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

import com.cyberops.portal.user.PersonRef;
import com.cyberops.portal.user.UserProfileRepository;
import com.cyberops.portal.activity.ActivityDtos.ActivitySummary;

@Repository
public class ActivityRepository {

	private final NamedParameterJdbcTemplate jdbc;

	public ActivityRepository(NamedParameterJdbcTemplate jdbc) {
		this.jdbc = jdbc;
	}

	private static final String BASE = """
			SELECT a.id, a.activity_name, a.activity_description, a.activity_date, a.location, a.activity_type,
			       a.participation_type, a.contact_person_id, cp.username AS cp_username, %s AS cp_display,
			       a.created_by, cb.username AS cb_username, %s AS cb_display
			FROM activity a
			LEFT JOIN app_user cp ON cp.id = a.contact_person_id
			LEFT JOIN app_user cb ON cb.id = a.created_by
			""".formatted(PersonRef.displayNameSql("cp"), PersonRef.displayNameSql("cb"));

	/** scope: upcoming | past | mine. */
	public List<ActivitySummary> list(String scope, long meId) {
		String where = switch (scope) {
			case "past" -> "WHERE a.activity_date < current_localtimestamp() ORDER BY a.activity_date DESC LIMIT 10";
			case "mine" -> "WHERE EXISTS (SELECT 1 FROM activity_attendee aa WHERE aa.activity_id = a.id"
					+ " AND aa.user_id = :me) ORDER BY a.activity_date DESC";
			default -> "WHERE a.activity_date >= current_localtimestamp() ORDER BY a.activity_date ASC";
		};
		return query(BASE + where, new MapSqlParameterSource("me", meId), meId);
	}

	public Optional<ActivitySummary> find(long id, long meId) {
		return query(BASE + "WHERE a.id = :id", new MapSqlParameterSource("id", id), meId).stream().findFirst();
	}

	private List<ActivitySummary> query(String sql, MapSqlParameterSource p, long meId) {
		record Row(long id, String name, String desc, java.sql.Timestamp date, String loc, String type, String part,
				PersonRef cp, PersonRef cb) {
		}
		List<Row> rows = jdbc.query(sql, p, (rs, i) -> {
			long cpId = rs.getLong("contact_person_id");
			PersonRef cp = rs.wasNull() || rs.getString("cp_username") == null ? null
					: new PersonRef(cpId, rs.getString("cp_username"), rs.getString("cp_display"));
			long cbId = rs.getLong("created_by");
			PersonRef cb = rs.wasNull() || rs.getString("cb_username") == null ? null
					: new PersonRef(cbId, rs.getString("cb_username"), rs.getString("cb_display"));
			return new Row(rs.getLong("id"), rs.getString("activity_name"), nz(rs.getString("activity_description")),
					rs.getTimestamp("activity_date"), nz(rs.getString("location")), rs.getString("activity_type"),
					rs.getString("participation_type"), cp, cb);
		});
		List<ActivitySummary> out = new ArrayList<>();
		for (Row r : rows) {
			List<PersonRef> attendees = attendees(r.id());
			boolean joined = attendees.stream().anyMatch(a -> a.id() == meId);
			out.add(new ActivitySummary(r.id(), r.name(), r.desc(), UserProfileRepository.toOffset(r.date()), r.loc(),
					r.type(), r.part(), r.cp(), r.cb(), attendees, joined));
		}
		return out;
	}

	public List<PersonRef> attendees(long activityId) {
		return jdbc.query("""
				SELECT u.id, u.username, %s AS display_name FROM activity_attendee aa
				JOIN app_user u ON u.id = aa.user_id WHERE aa.activity_id = :a ORDER BY display_name"""
				.formatted(PersonRef.displayNameSql("u")), Map.of("a", activityId),
				(rs, i) -> new PersonRef(rs.getLong("id"), rs.getString("username"), rs.getString("display_name")));
	}

	public long insert(String name, String description, LocalDateTime date, String location, String type,
			String participationType, Long contactPersonId, long createdBy) {
		MapSqlParameterSource p = new MapSqlParameterSource("n", name).addValue("d", description)
				.addValue("dt", date).addValue("l", location).addValue("t", type).addValue("pt", participationType)
				.addValue("cp", contactPersonId).addValue("cb", createdBy);
		return jdbc.queryForObject("""
				INSERT INTO activity (activity_name, activity_description, activity_date, location, activity_type,
				                      participation_type, contact_person_id, created_by)
				VALUES (:n, :d, :dt, :l, :t, :pt, :cp, :cb) RETURNING id""", p, Long.class);
	}

	public boolean exists(long activityId) {
		Integer c = jdbc.queryForObject("SELECT count(*) FROM activity WHERE id = :id", Map.of("id", activityId),
				Integer.class);
		return c != null && c > 0;
	}

	public boolean userExists(long userId) {
		Integer c = jdbc.queryForObject("SELECT count(*) FROM app_user WHERE id = :id AND is_active",
				Map.of("id", userId), Integer.class);
		return c != null && c > 0;
	}

	public void addAttendee(long activityId, long userId) {
		jdbc.update("INSERT OR IGNORE INTO activity_attendee (activity_id, user_id) VALUES (:a, :u)",
				Map.of("a", activityId, "u", userId));
	}

	public int removeAttendee(long activityId, long userId) {
		return jdbc.update("DELETE FROM activity_attendee WHERE activity_id = :a AND user_id = :u",
				Map.of("a", activityId, "u", userId));
	}

	private static String nz(String s) {
		return s == null ? "" : s;
	}
}

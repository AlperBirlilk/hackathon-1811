package com.cyberops.portal.task;

import java.sql.ResultSet;
import java.sql.SQLException;

/** UserRef: { id, username, displayName }. */
public record UserRef(long id, String username, String displayName) {

	public static String displayName(String username, String firstName, String lastName) {
		String full = ((firstName == null ? "" : firstName) + " " + (lastName == null ? "" : lastName)).trim();
		return full.isEmpty() ? username : full;
	}

	/** Maps columns {prefix}id, {prefix}username, {prefix}first_name, {prefix}last_name; null if no user. */
	public static UserRef map(ResultSet rs, String prefix) throws SQLException {
		long id = rs.getLong(prefix + "id");
		if (rs.wasNull()) {
			return null;
		}
		String username = rs.getString(prefix + "username");
		if (username == null) {
			return null;
		}
		return new UserRef(id, username,
				displayName(username, rs.getString(prefix + "first_name"), rs.getString(prefix + "last_name")));
	}
}

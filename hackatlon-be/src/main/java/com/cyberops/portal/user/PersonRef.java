package com.cyberops.portal.user;

/** UserRef in the API contract: {id, username, displayName}. */
public record PersonRef(long id, String username, String displayName) {

	/** SQL expression for displayName on an app_user alias (first + last, falling back to username). */
	public static String displayNameSql(String alias) {
		return "coalesce(nullif(trim(coalesce(" + alias + ".first_name,'') || ' ' || coalesce(" + alias
				+ ".last_name,'')), ''), " + alias + ".username)";
	}
}

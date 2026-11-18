package com.cyberops.portal.auth;

import java.util.Set;

/** Authenticated portal user; permissions are always loaded fresh from DuckDB, never from JWT claims. */
public record CurrentUser(long id, String username, Set<String> permissions) {

	public boolean hasPerm(String code) {
		return permissions.contains(code);
	}
}

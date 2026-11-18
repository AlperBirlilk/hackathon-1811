package com.cyberops.portal.auth;

import java.util.List;

/** Response shape of POST /internal/users/sync and GET /api/me. */
public record UserProfile(long id, String username, String displayName, String title, List<String> permissions,
		Long managerId, boolean isManager, boolean isOnLeave) {
}

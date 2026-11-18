package com.cyberops.portal.auth;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;

import com.cyberops.portal.common.ForbiddenException;

/**
 * Resolves the caller from the JWT {@code sub} claim (app_user.id) and loads permissions fresh from DuckDB.
 * Usage in controllers/services: {@code CurrentUser me = currentUserService.get(); if (!me.hasPerm(...)) ...}
 */
@Service
public class CurrentUserService {

	private final UserAccountRepository users;

	public CurrentUserService(UserAccountRepository users) {
		this.users = users;
	}

	public CurrentUser get() {
		Authentication auth = SecurityContextHolder.getContext().getAuthentication();
		if (auth == null || !(auth.getPrincipal() instanceof Jwt jwt)) {
			throw new ForbiddenException("Kimlik doğrulanmadı.");
		}
		long id;
		try {
			id = Long.parseLong(jwt.getSubject());
		}
		catch (NumberFormatException e) {
			throw new ForbiddenException("Geçersiz token subject.");
		}
		String username = users.username(id);
		if (username == null) {
			throw new ForbiddenException("Kullanıcı bulunamadı veya pasif.");
		}
		return new CurrentUser(id, username, users.permissionCodes(id));
	}

	/** Throws ForbiddenException unless the current user has the given permission code. */
	public CurrentUser require(String permissionCode) {
		CurrentUser me = get();
		if (!me.hasPerm(permissionCode)) {
			throw new ForbiddenException();
		}
		return me;
	}
}

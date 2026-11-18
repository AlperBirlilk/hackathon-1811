package com.cyberops.portal.auth;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import com.cyberops.portal.common.NotFoundException;
import com.cyberops.portal.common.PermissionCodes;

/** Minimal app_user access needed by auth (sync, /api/me, permission lookup). */
@Repository
public class UserAccountRepository {

	private final NamedParameterJdbcTemplate jdbc;

	public UserAccountRepository(NamedParameterJdbcTemplate jdbc) {
		this.jdbc = jdbc;
	}

	public Set<String> permissionCodes(long userId) {
		List<String> codes = jdbc.queryForList("""
				SELECT pt.code FROM user_permission up
				JOIN permission_type pt ON pt.id = up.permission_type_id
				WHERE up.user_id = :id ORDER BY pt.id""", Map.of("id", userId), String.class);
		return new LinkedHashSet<>(codes);
	}

	public Optional<Long> findIdByUsername(String username) {
		return jdbc.queryForList("SELECT id FROM app_user WHERE username = :u", Map.of("u", username), Long.class)
				.stream().findFirst();
	}

	@Transactional
	public long upsert(String username, String firstName, String lastName, String email, String authSource) {
		Map<String, Object> p = new java.util.HashMap<>();
		p.put("u", username);
		p.put("fn", firstName == null ? "" : firstName);
		p.put("ln", lastName == null ? "" : lastName);
		p.put("em", email == null ? "" : email);
		p.put("src", authSource == null || authSource.isBlank() ? "LDAP" : authSource);
		Optional<Long> existing = findIdByUsername(username);
		if (existing.isPresent()) {
			p.put("id", existing.get());
			jdbc.update("""
					UPDATE app_user SET first_name = :fn, last_name = :ln, email = :em, auth_source = :src
					WHERE id = :id""", p);
			return existing.get();
		}
		return jdbc.queryForObject("""
				INSERT INTO app_user (username, first_name, last_name, email, auth_source, is_active, is_on_leave)
				VALUES (:u, :fn, :ln, :em, :src, TRUE, FALSE) RETURNING id""", p, Long.class);
	}

	public UserProfile profile(long userId) {
		List<UserProfile> rows = jdbc.query(
				"SELECT id, username, first_name, last_name, title, manager_id, is_on_leave FROM app_user WHERE id = :id",
				Map.of("id", userId), (rs, i) -> {
					String full = (nz(rs.getString("first_name")) + " " + nz(rs.getString("last_name"))).trim();
					long mgr = rs.getLong("manager_id");
					Long managerId = rs.wasNull() ? null : mgr;
					List<String> perms = List.copyOf(permissionCodes(userId));
					return new UserProfile(rs.getLong("id"), rs.getString("username"),
							full.isEmpty() ? rs.getString("username") : full, rs.getString("title"), perms, managerId,
							perms.contains(PermissionCodes.ROLE_MANAGEMENT), rs.getBoolean("is_on_leave"));
				});
		if (rows.isEmpty()) {
			throw new NotFoundException("Kullanıcı bulunamadı: " + userId);
		}
		return rows.get(0);
	}

	public String username(long userId) {
		return jdbc.queryForList("SELECT username FROM app_user WHERE id = :id AND is_active", Map.of("id", userId),
				String.class).stream().findFirst().orElse(null);
	}

	private static String nz(String s) {
		return s == null ? "" : s;
	}
}

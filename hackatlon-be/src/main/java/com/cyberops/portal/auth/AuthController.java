package com.cyberops.portal.auth;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.cyberops.portal.common.NotFoundException;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;

@RestController
public class AuthController {

	public record SyncRequest(@NotBlank String username, String firstName, String lastName, String email,
			String authSource) {
	}

	private final UserAccountRepository users;
	private final CurrentUserService currentUser;
	private final JwtService jwtService;

	public AuthController(UserAccountRepository users, CurrentUserService currentUser, JwtService jwtService) {
		this.users = users;
		this.currentUser = currentUser;
		this.jwtService = jwtService;
	}

	/** Called by Django after LDAP login (X-Service-Key). Upserts app_user by username. */
	@PostMapping("/internal/users/sync")
	public UserProfile sync(@Valid @RequestBody SyncRequest req) {
		long id = users.upsert(req.username().trim(), req.firstName(), req.lastName(), req.email(), req.authSource());
		return users.profile(id);
	}

	@GetMapping("/api/me")
	public UserProfile me() {
		return users.profile(currentUser.get().id());
	}

	/** DEV ONLY: signed JWT for curl testing (X-Service-Key required). */
	@GetMapping("/internal/dev/token")
	public Map<String, Object> devToken(@RequestParam String username) {
		long id = users.findIdByUsername(username)
				.orElseThrow(() -> new NotFoundException("Kullanıcı bulunamadı: " + username));
		return Map.of("token", jwtService.issue(id, username, 12 * 60), "userId", id, "username", username);
	}
}

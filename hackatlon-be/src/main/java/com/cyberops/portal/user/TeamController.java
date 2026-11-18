package com.cyberops.portal.user;

import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.cyberops.portal.auth.CurrentUserService;
import com.cyberops.portal.user.UserDtos.AddMember;
import com.cyberops.portal.user.UserDtos.PermissionRow;
import com.cyberops.portal.user.UserDtos.PermissionUpdate;
import com.cyberops.portal.user.UserDtos.TeamMember;

import jakarta.validation.Valid;

/** /api/team/** — ROLE_MANAGEMENT (checked in UserProfileService). */
@RestController
public class TeamController {

	private final UserProfileService service;
	private final CurrentUserService currentUser;

	public TeamController(UserProfileService service, CurrentUserService currentUser) {
		this.service = service;
		this.currentUser = currentUser;
	}

	@GetMapping("/api/team")
	public List<TeamMember> team() {
		return service.team(currentUser.get());
	}

	@GetMapping("/api/team/candidates")
	public List<PersonRef> candidates() {
		return service.candidates(currentUser.get());
	}

	@PostMapping("/api/team/members")
	public ResponseEntity<Void> add(@Valid @RequestBody AddMember body) {
		service.addMember(currentUser.get(), body.userId());
		return ResponseEntity.noContent().build();
	}

	@DeleteMapping("/api/team/members/{userId}")
	public ResponseEntity<Void> remove(@PathVariable long userId) {
		service.removeMember(currentUser.get(), userId);
		return ResponseEntity.noContent().build();
	}

	@GetMapping("/api/team/members/{userId}/permissions")
	public List<PermissionRow> permissions(@PathVariable long userId) {
		return service.memberPermissions(currentUser.get(), userId);
	}

	@PutMapping("/api/team/members/{userId}/permissions")
	public List<PermissionRow> updatePermissions(@PathVariable long userId, @Valid @RequestBody PermissionUpdate body) {
		return service.updateMemberPermissions(currentUser.get(), userId, body.codes());
	}
}

package com.cyberops.portal.user;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.cyberops.portal.auth.CurrentUserService;
import com.cyberops.portal.user.UserDtos.Profile;
import com.cyberops.portal.user.UserDtos.ProfileUpdate;
import com.cyberops.portal.user.UserDtos.Skill;
import com.cyberops.portal.user.UserDtos.SkillCreate;

import jakarta.validation.Valid;

/** /api/users/{id}, /api/users/me (PATCH) and skills. GET /api/users (list) is owned elsewhere. */
@RestController
public class UserProfileController {

	private final UserProfileService service;
	private final CurrentUserService currentUser;

	public UserProfileController(UserProfileService service, CurrentUserService currentUser) {
		this.service = service;
		this.currentUser = currentUser;
	}

	@GetMapping("/api/users/{id:\\d+}")
	public Profile profile(@PathVariable long id) {
		return service.profile(currentUser.get(), id);
	}

	@PatchMapping("/api/users/me")
	public Profile updateMe(@Valid @RequestBody ProfileUpdate body) {
		return service.updateMe(currentUser.get(), body);
	}

	@GetMapping("/api/users/{id:\\d+}/skills")
	public List<Skill> skills(@PathVariable long id) {
		return service.skills(currentUser.get(), id);
	}

	@PostMapping("/api/users/me/skills")
	public ResponseEntity<Skill> addSkill(@Valid @RequestBody SkillCreate body) {
		return ResponseEntity.status(HttpStatus.CREATED).body(service.addSkill(currentUser.get(), body));
	}

	@DeleteMapping("/api/users/me/skills/{skillId}")
	public ResponseEntity<Void> deleteSkill(@PathVariable long skillId) {
		service.deleteSkill(currentUser.get(), skillId);
		return ResponseEntity.noContent().build();
	}
}

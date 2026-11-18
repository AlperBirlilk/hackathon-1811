package com.cyberops.portal.activity;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.cyberops.portal.activity.ActivityDtos.ActivityCreate;
import com.cyberops.portal.activity.ActivityDtos.ActivitySummary;
import com.cyberops.portal.activity.ActivityDtos.JoinResult;
import com.cyberops.portal.auth.CurrentUserService;

import jakarta.validation.Valid;

@RestController
public class ActivityController {

	private final ActivityService service;
	private final CurrentUserService currentUser;

	public ActivityController(ActivityService service, CurrentUserService currentUser) {
		this.service = service;
		this.currentUser = currentUser;
	}

	@GetMapping("/api/activities")
	public List<ActivitySummary> list(@RequestParam(required = false) String scope) {
		return service.list(currentUser.get(), scope);
	}

	@PostMapping("/api/activities")
	public ResponseEntity<ActivitySummary> create(@Valid @RequestBody ActivityCreate body) {
		return ResponseEntity.status(HttpStatus.CREATED).body(service.create(currentUser.get(), body));
	}

	@PostMapping("/api/activities/{id}/join")
	public JoinResult join(@PathVariable long id) {
		return new JoinResult(service.toggleJoin(currentUser.get(), id));
	}
}

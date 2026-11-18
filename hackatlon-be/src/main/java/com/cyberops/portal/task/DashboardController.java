package com.cyberops.portal.task;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import com.cyberops.portal.auth.CurrentUserService;
import com.cyberops.portal.task.DashboardDtos.Dashboard;

@RestController
public class DashboardController {

	private final DashboardService service;
	private final CurrentUserService currentUser;

	public DashboardController(DashboardService service, CurrentUserService currentUser) {
		this.service = service;
		this.currentUser = currentUser;
	}

	@GetMapping("/api/dashboard")
	public Dashboard dashboard() {
		return service.get(currentUser.get());
	}
}

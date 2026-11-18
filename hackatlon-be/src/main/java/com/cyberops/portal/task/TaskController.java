package com.cyberops.portal.task;

import java.util.List;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.cyberops.portal.auth.CurrentUserService;
import com.cyberops.portal.task.TaskDtos.HistoryEntry;
import com.cyberops.portal.task.TaskDtos.StatusRequest;
import com.cyberops.portal.task.TaskDtos.TaskCreate;
import com.cyberops.portal.task.TaskDtos.TaskDetail;
import com.cyberops.portal.task.TaskDtos.TaskSummary;

@RestController
public class TaskController {

	private final TaskService service;
	private final CurrentUserService currentUser;

	public TaskController(TaskService service, CurrentUserService currentUser) {
		this.service = service;
		this.currentUser = currentUser;
	}

	@GetMapping("/api/tasks")
	public List<TaskSummary> list(@RequestParam(required = false) String status,
			@RequestParam(required = false) String severity, @RequestParam(required = false) String q,
			@RequestParam(required = false) Long assigneeId, @RequestParam(required = false) Boolean overdue) {
		return service.list(currentUser.get(), status, severity, q, assigneeId, overdue);
	}

	@PostMapping("/api/tasks")
	@ResponseStatus(HttpStatus.CREATED)
	public TaskDetail create(@RequestBody TaskCreate req) {
		return service.create(currentUser.get(), req);
	}

	@GetMapping("/api/tasks/{id}")
	public TaskDetail get(@PathVariable long id) {
		return service.get(currentUser.get(), id);
	}

	@PatchMapping("/api/tasks/{id}")
	public TaskDetail update(@PathVariable long id, @RequestBody Map<String, Object> body) {
		return service.update(currentUser.get(), id, body);
	}

	@PostMapping("/api/tasks/{id}/status")
	public TaskDetail status(@PathVariable long id, @RequestBody StatusRequest req) {
		return service.changeStatus(currentUser.get(), id, req.status());
	}

	@GetMapping("/api/tasks/{id}/history")
	public List<HistoryEntry> history(@PathVariable long id) {
		return service.history(currentUser.get(), id);
	}

	/** Active users for assignee pickers. Only this exact path; /api/users/{id} etc. belong to the user package. */
	@GetMapping("/api/users")
	public List<UserRef> users() {
		currentUser.get();
		return service.activeUsers();
	}
}

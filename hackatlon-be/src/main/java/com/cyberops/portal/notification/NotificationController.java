package com.cyberops.portal.notification;

import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.cyberops.portal.auth.CurrentUserService;

@RestController
@RequestMapping("/api/notifications")
public class NotificationController {

	private final NotificationService service;
	private final CurrentUserService currentUser;

	public NotificationController(NotificationService service, CurrentUserService currentUser) {
		this.service = service;
		this.currentUser = currentUser;
	}

	@GetMapping
	public List<NotificationDtos.Notification> list(@RequestParam(defaultValue = "false") boolean unread) {
		return service.list(currentUser.get().id(), unread);
	}

	@GetMapping("/unread-count")
	public NotificationDtos.Count unreadCount() {
		return new NotificationDtos.Count(service.unreadCount(currentUser.get().id()));
	}

	@PostMapping("/{id}/read")
	public ResponseEntity<Void> read(@PathVariable long id) {
		service.markRead(id, currentUser.get().id());
		return ResponseEntity.noContent().build();
	}

	@PostMapping("/read-all")
	public ResponseEntity<Void> readAll() {
		service.markAllRead(currentUser.get().id());
		return ResponseEntity.noContent().build();
	}
}

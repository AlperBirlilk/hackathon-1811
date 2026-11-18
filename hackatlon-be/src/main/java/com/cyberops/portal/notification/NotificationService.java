package com.cyberops.portal.notification;

import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cyberops.portal.common.NotFoundException;

@Service
public class NotificationService {

	private final NotificationRepository repo;

	public NotificationService(NotificationRepository repo) {
		this.repo = repo;
	}

	public List<NotificationDtos.Notification> list(long userId, boolean unread) {
		return repo.list(userId, unread);
	}

	public long unreadCount(long userId) {
		return repo.unreadCount(userId);
	}

	@Transactional
	public void markRead(long id, long userId) {
		if (!repo.markRead(id, userId)) {
			throw new NotFoundException("Bildirim bulunamadı.");
		}
	}

	@Transactional
	public void markAllRead(long userId) {
		repo.markAllRead(userId);
	}
}

package com.cyberops.portal.notification;

import java.time.OffsetDateTime;

import com.fasterxml.jackson.annotation.JsonProperty;

public final class NotificationDtos {

	private NotificationDtos() {
	}

	public record TaskRef(long id, String code) {
	}

	public record Notification(long id, String message, TaskRef task, @JsonProperty("isRead") boolean isRead,
			OffsetDateTime createDate) {
	}

	public record Count(long count) {
	}
}

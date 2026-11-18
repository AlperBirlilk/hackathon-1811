package com.cyberops.portal.activity;

import java.time.OffsetDateTime;
import java.util.List;

import com.cyberops.portal.user.PersonRef;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public final class ActivityDtos {

	private ActivityDtos() {
	}

	public record ActivityCreate(@NotBlank @Size(max = 200) String name, @Size(max = 4000) String description,
			@NotBlank String date, @Size(max = 200) String location, String type, String participationType,
			Long contactPersonId, List<Long> attendeeIds) {
	}

	public record ActivitySummary(long id, String name, String description, OffsetDateTime date, String location,
			String type, String participationType, PersonRef contactPerson, PersonRef createdBy,
			List<PersonRef> attendees, boolean joined) {
	}

	public record JoinResult(boolean joined) {
	}
}

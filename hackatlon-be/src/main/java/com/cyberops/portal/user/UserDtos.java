package com.cyberops.portal.user;

import java.time.OffsetDateTime;
import java.util.List;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

/** Request/response records for user, skill and team endpoints. */
public final class UserDtos {

	private UserDtos() {
	}

	public record Profile(long id, String username, String firstName, String lastName, String displayName,
			String email, String title, String department, String phone, String location, String bio,
			PersonRef manager, boolean isOnLeave, List<String> permissions) {
	}

	public record ProfileUpdate(@Size(max = 100) String firstName, @Size(max = 100) String lastName,
			@Size(max = 200) String title, @Size(max = 200) String department, @Size(max = 200) String location,
			@Size(max = 200) String email, @Size(max = 50) String phone, @Size(max = 2000) String bio,
			Boolean isOnLeave) {
	}

	public record Skill(long id, String skillName, String kind, OffsetDateTime createDate) {
	}

	public record SkillCreate(@NotBlank @Size(max = 200) String skillName, String kind) {
	}

	public record TeamMember(PersonRef user, String title, boolean isOnLeave, List<String> permissions,
			long openCount, long progressCount, long doneCount, long overdueCount) {
	}

	public record AddMember(@NotNull Long userId) {
	}

	public record PermissionRow(String code, String name, boolean granted, boolean grantable) {
	}

	public record PermissionUpdate(@NotNull List<String> codes) {
	}
}

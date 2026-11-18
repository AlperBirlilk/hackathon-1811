package com.cyberops.portal.task;

import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;

import com.cyberops.portal.auth.CurrentUser;
import com.cyberops.portal.common.PermissionCodes;

/**
 * Task visibility rule (single source of truth — use it in every task query):
 * <ul>
 * <li>Users with {@code TASK_MANAGEMENT} see all tasks (directors have all perms, so they see all too).</li>
 * <li>Everyone else sees only tasks where they are an assignee ({@code task_assignee}),
 * the backup assignee ({@code task.backup_assignee_id}) or the creator ({@code task.created_by}).</li>
 * </ul>
 * Usage (task table must be aliased {@code t}):
 * <pre>
 * MapSqlParameterSource p = new MapSqlParameterSource();
 * String sql = "SELECT t.* FROM task t WHERE " + TaskVisibility.where(user, p) + " ORDER BY t.modified_date DESC";
 * jdbc.query(sql, p, mapper);
 * </pre>
 */
public final class TaskVisibility {

	private TaskVisibility() {
	}

	public static boolean seesAll(CurrentUser user) {
		return user.hasPerm(PermissionCodes.TASK_MANAGEMENT);
	}

	/** Returns a parameterized SQL predicate on alias {@code t}; adds {@code :visUserId} to params. */
	public static String where(CurrentUser user, MapSqlParameterSource params) {
		if (seesAll(user)) {
			return "1=1";
		}
		params.addValue("visUserId", user.id());
		return "(t.created_by = :visUserId OR t.backup_assignee_id = :visUserId"
				+ " OR EXISTS (SELECT 1 FROM task_assignee ta WHERE ta.task_id = t.id AND ta.user_id = :visUserId))";
	}
}

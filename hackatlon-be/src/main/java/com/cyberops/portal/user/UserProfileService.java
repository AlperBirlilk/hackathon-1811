package com.cyberops.portal.user;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cyberops.portal.auth.CurrentUser;
import com.cyberops.portal.common.ForbiddenException;
import com.cyberops.portal.common.NotFoundException;
import com.cyberops.portal.common.PermissionCodes;
import com.cyberops.portal.user.UserDtos.PermissionRow;
import com.cyberops.portal.user.UserDtos.Profile;
import com.cyberops.portal.user.UserDtos.ProfileUpdate;
import com.cyberops.portal.user.UserDtos.Skill;
import com.cyberops.portal.user.UserDtos.SkillCreate;
import com.cyberops.portal.user.UserDtos.TeamMember;
import com.cyberops.portal.user.UserProfileRepository.PermissionType;
import com.cyberops.portal.user.UserProfileRepository.ProfileRow;

/** Profile, skill and team rules. All scope/permission checks live here. */
@Service
public class UserProfileService {

	private static final Set<String> SKILL_KINDS = Set.of("SKILL", "CERTIFICATE");
	private static final List<String> ALL_PERMS = List.of(PermissionCodes.TASK_MANAGEMENT,
			PermissionCodes.ACTIVITY_MANAGEMENT, PermissionCodes.ROLE_MANAGEMENT, PermissionCodes.REPORT_ANALYSIS,
			PermissionCodes.DATA_ACCESS);

	private final UserProfileRepository repo;

	public UserProfileService(UserProfileRepository repo) {
		this.repo = repo;
	}

	public static boolean isDirector(CurrentUser me) {
		return me.permissions().containsAll(ALL_PERMS);
	}

	// ---- profile ----

	public Profile profile(CurrentUser me, long userId) {
		ProfileRow row = viewable(me, userId);
		return toProfile(row);
	}

	@Transactional
	public Profile updateMe(CurrentUser me, ProfileUpdate update) {
		repo.updateProfile(me.id(), update);
		return toProfile(repo.findProfile(me.id()).orElseThrow(() -> new NotFoundException("Kullanıcı bulunamadı.")));
	}

	public List<Skill> skills(CurrentUser me, long userId) {
		viewable(me, userId);
		return repo.skills(userId);
	}

	@Transactional
	public Skill addSkill(CurrentUser me, SkillCreate req) {
		String kind = req.kind() == null || req.kind().isBlank() ? "SKILL" : req.kind().trim().toUpperCase();
		if (!SKILL_KINDS.contains(kind)) {
			throw new IllegalArgumentException("Geçersiz yetkinlik türü: " + req.kind());
		}
		return repo.insertSkill(me.id(), req.skillName().trim(), kind);
	}

	@Transactional
	public void deleteSkill(CurrentUser me, long skillId) {
		if (repo.deleteSkill(me.id(), skillId) == 0) {
			throw new NotFoundException("Yetkinlik bulunamadı.");
		}
	}

	private ProfileRow viewable(CurrentUser me, long userId) {
		ProfileRow row = repo.findProfile(userId).orElseThrow(() -> new NotFoundException("Kullanıcı bulunamadı."));
		boolean allowed = row.id() == me.id() || (row.managerId() != null && row.managerId() == me.id())
				|| me.hasPerm(PermissionCodes.ROLE_MANAGEMENT);
		if (!allowed) {
			throw new ForbiddenException("Bu profili görüntüleme yetkiniz yok.");
		}
		return row;
	}

	private Profile toProfile(ProfileRow r) {
		PersonRef manager = r.managerId() == null ? null : repo.findRef(r.managerId()).orElse(null);
		return new Profile(r.id(), r.username(), r.firstName(), r.lastName(), r.displayName(), r.email(), r.title(),
				r.department(), r.phone(), r.location(), r.bio(), manager, r.isOnLeave(),
				repo.permissionCodes(r.id()));
	}

	// ---- team ----

	public List<TeamMember> team(CurrentUser me) {
		requireRoleMgmt(me);
		Long managerFilter = isDirector(me) ? null : me.id();
		return repo.members(managerFilter, me.id()).stream()
				.map(m -> new TeamMember(m.user(), m.title(), m.isOnLeave(), repo.permissionCodes(m.user().id()),
						m.openCount(), m.progressCount(), m.doneCount(), m.overdueCount()))
				.toList();
	}

	public List<PersonRef> candidates(CurrentUser me) {
		requireRoleMgmt(me);
		return repo.candidates(me.id());
	}

	@Transactional
	public void addMember(CurrentUser me, long userId) {
		requireRoleMgmt(me);
		if (userId == me.id()) {
			throw new IllegalArgumentException("Kendinizi ekibinize ekleyemezsiniz.");
		}
		ProfileRow row = repo.findProfile(userId).orElseThrow(() -> new NotFoundException("Kullanıcı bulunamadı."));
		if (!row.isActive() || row.managerId() != null || repo.setManagerIfNone(userId, me.id()) == 0) {
			throw new IllegalArgumentException("Kullanıcının zaten bir yöneticisi var veya aktif değil.");
		}
	}

	@Transactional
	public void removeMember(CurrentUser me, long userId) {
		requireRoleMgmt(me);
		requireTeamMember(me, userId);
		repo.clearManager(userId);
	}

	public List<PermissionRow> memberPermissions(CurrentUser me, long userId) {
		requireRoleMgmt(me);
		requireTeamMember(me, userId);
		return permissionRows(me, userId);
	}

	@Transactional
	public List<PermissionRow> updateMemberPermissions(CurrentUser me, long userId, List<String> codes) {
		requireRoleMgmt(me);
		requireTeamMember(me, userId);
		List<PermissionType> types = repo.permissionTypes();
		Set<String> known = new HashSet<>();
		types.forEach(t -> known.add(t.code()));
		Set<String> desired = new HashSet<>();
		for (String c : codes) {
			if (c == null || !known.contains(c)) {
				throw new IllegalArgumentException("Geçersiz yetki kodu: " + c);
			}
			desired.add(c);
		}
		Set<String> current = new HashSet<>(repo.permissionCodes(userId));
		for (PermissionType t : types) {
			boolean want = desired.contains(t.code());
			boolean has = current.contains(t.code());
			if (want == has) {
				continue;
			}
			// privilege-escalation guard: only codes the caller holds may be granted or revoked
			if (!me.hasPerm(t.code())) {
				throw new ForbiddenException("Sahip olmadığınız yetkiyi veremez veya geri alamazsınız: " + t.code());
			}
			if (want) {
				repo.grant(userId, t.id(), me.id());
			}
			else {
				repo.revoke(userId, t.id());
			}
		}
		return permissionRows(me, userId);
	}

	private List<PermissionRow> permissionRows(CurrentUser me, long userId) {
		Set<String> granted = new HashSet<>(repo.permissionCodes(userId));
		return repo.permissionTypes().stream()
				.map(t -> new PermissionRow(t.code(), t.name(), granted.contains(t.code()), me.hasPerm(t.code())))
				.toList();
	}

	private void requireRoleMgmt(CurrentUser me) {
		if (!me.hasPerm(PermissionCodes.ROLE_MANAGEMENT)) {
			throw new ForbiddenException();
		}
	}

	private void requireTeamMember(CurrentUser me, long userId) {
		ProfileRow row = repo.findProfile(userId).orElseThrow(() -> new NotFoundException("Kullanıcı bulunamadı."));
		if (userId == me.id()) {
			throw new ForbiddenException("Kendi yetkilerinizi/ekip kaydınızı değiştiremezsiniz.");
		}
		if (isDirector(me)) {
			return;
		}
		if (row.managerId() == null || row.managerId() != me.id()) {
			throw new NotFoundException("Kullanıcı ekibinizde değil.");
		}
	}
}

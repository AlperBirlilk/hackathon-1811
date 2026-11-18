-- Demo seed (mirrors hackatlon-django seed.py). Idempotent: fixed ids + INSERT OR IGNORE.
-- No passwords: authentication is done by Django (LDAP).
-- Users: 1 direktor, 2 yonetici, 3 mert, 4 alper, 5 berkay, 6 aykun

INSERT OR IGNORE INTO permission_type (id, code, permission_name, description) VALUES
 (1, 'TASK_MANAGEMENT', 'Task Management', 'Tüm taskları görme / oluşturma / atama'),
 (2, 'ACTIVITY_MANAGEMENT', 'Activity Management', 'Etkinlik oluşturma ve yönetme'),
 (3, 'ROLE_MANAGEMENT', 'Role Management', 'Ekip ve yetki yönetimi (Yönetici)'),
 (4, 'REPORT_ANALYSIS', 'Report & Analysis', 'Rapor ve analiz panellerine erişim'),
 (5, 'DATA_ACCESS', 'Data Access', 'Veri paylaşımı alanına erişim');

INSERT OR IGNORE INTO app_user (id, username, first_name, last_name, email, title, department, phone, location, manager_id, auth_source) VALUES
 (1, 'direktor', 'Ahmet', 'Öztürk', 'direktor@cyberops.local', 'Siber Güvenlik Direktörü', 'Siber Güvenlik Operasyonları', '+90 555 000 00 00', 'İstanbul', NULL, 'LDAP'),
 (2, 'yonetici', 'Selin', 'Kaya', 'yonetici@cyberops.local', 'SOC Manager', 'Siber Güvenlik Operasyonları', '+90 555 000 00 00', 'İstanbul', 1, 'LDAP'),
 (3, 'mert', 'Mert', 'Demir', 'mert@cyberops.local', 'SOC Analyst L2', 'Siber Güvenlik Operasyonları', '+90 555 000 00 00', 'İstanbul', 2, 'LDAP'),
 (4, 'alper', 'Alper', 'Çalbırlık', 'alper@cyberops.local', 'Penetration Tester', 'Siber Güvenlik Operasyonları', '+90 555 000 00 00', 'İstanbul', 2, 'LDAP'),
 (5, 'berkay', 'Berkay', 'Yıldız', 'berkay@cyberops.local', 'Malware Analyst', 'Siber Güvenlik Operasyonları', '+90 555 000 00 00', 'İstanbul', 2, 'LDAP'),
 (6, 'aykun', 'Aykun', 'Arslan', 'aykun@cyberops.local', 'Cloud Security Engineer', 'Siber Güvenlik Operasyonları', '+90 555 000 00 00', 'İstanbul', 2, 'LDAP');

INSERT OR IGNORE INTO user_permission (user_id, permission_type_id, granted_by) VALUES
 (1, 1, NULL), (1, 2, NULL), (1, 3, NULL), (1, 4, NULL), (1, 5, NULL),
 (2, 1, 1), (2, 2, 1), (2, 3, 1), (2, 4, 1), (2, 5, 1),
 (3, 5, 2),
 (4, 1, 2),
 (5, 4, 2),
 (6, 2, 2);

INSERT OR IGNORE INTO user_skill (id, user_id, skill_name, kind) VALUES
 (1, 2, 'Incident Response', 'SKILL'), (2, 2, 'Risk Yönetimi', 'SKILL'),
 (3, 2, 'CISSP', 'CERTIFICATE'), (4, 2, 'CISM', 'CERTIFICATE'),
 (5, 3, 'SIEM', 'SKILL'), (6, 3, 'Splunk', 'SKILL'), (7, 3, 'Threat Hunting', 'SKILL'),
 (8, 3, 'CySA+', 'CERTIFICATE'),
 (9, 4, 'Web App Pentest', 'SKILL'), (10, 4, 'Burp Suite', 'SKILL'), (11, 4, 'Python', 'SKILL'),
 (12, 4, 'OSCP', 'CERTIFICATE'), (13, 4, 'eWPTX', 'CERTIFICATE'),
 (14, 5, 'Reverse Engineering', 'SKILL'), (15, 5, 'IDA Pro', 'SKILL'), (16, 5, 'YARA', 'SKILL'),
 (17, 5, 'GREM', 'CERTIFICATE'),
 (18, 6, 'AWS Security', 'SKILL'), (19, 6, 'Kubernetes', 'SKILL'), (20, 6, 'Terraform', 'SKILL'),
 (21, 6, 'CCSP', 'CERTIFICATE'), (22, 6, 'AWS Security Specialty', 'CERTIFICATE'),
 (23, 1, 'Security Governance', 'SKILL'), (24, 1, 'CISSP', 'CERTIFICATE');

-- Tasks: due_date by SLA (CRITICAL +1d, HIGH +3d, MEDIUM +7d, LOW +14d from create).
-- Tasks 2 and 5 are created in the past so they are already OVERDUE (demo).
INSERT OR IGNORE INTO task (id, task_status, task_severity, task_title, task_description, due_date, backup_assignee_id, create_date, created_by, modified_date, modified_by) VALUES
 (1, 'IN_PROGRESS', 'CRITICAL', 'Phishing kampanyası analizi', 'Finans birimine gelen şüpheli e-postaların IOC çıkarımı.',
    current_timestamp + INTERVAL 1 DAY, 5, current_timestamp, 2, current_timestamp, 3),
 (2, 'OPEN', 'HIGH', 'CVE-2026-1123 yama takibi', 'Edge cihazlarda kritik RCE açığı için yama doğrulaması.',
    current_timestamp - INTERVAL 2 DAY, 4, current_timestamp - INTERVAL 5 DAY, 2, current_timestamp - INTERVAL 5 DAY, 2),
 (3, 'IN_PROGRESS', 'HIGH', 'Web uygulaması sızma testi', 'Müşteri portalı için OWASP Top 10 kapsamında test.',
    current_timestamp + INTERVAL 3 DAY, NULL, current_timestamp, 2, current_timestamp, 4),
 (4, 'OPEN', 'MEDIUM', 'SIEM korelasyon kuralları', 'Brute-force ve impossible travel kurallarının iyileştirilmesi.',
    current_timestamp + INTERVAL 7 DAY, 5, current_timestamp, 2, current_timestamp, 2),
 (5, 'OPEN', 'CRITICAL', 'Ransomware örneği tersine mühendislik', 'Karantinadaki örneğin C2 adreslerinin çıkarılması.',
    current_timestamp - INTERVAL 1 DAY, 3, current_timestamp - INTERVAL 2 DAY, 2, current_timestamp - INTERVAL 2 DAY, 2),
 (6, 'DONE', 'MEDIUM', 'S3 bucket erişim denetimi', 'Public erişime açık bucket taraması.',
    current_timestamp + INTERVAL 7 DAY, NULL, current_timestamp, 2, current_timestamp, 6),
 (7, 'DONE', 'LOW', 'Firewall kural temizliği', 'Kullanılmayan any-any kuralların kaldırılması.',
    current_timestamp + INTERVAL 14 DAY, NULL, current_timestamp, 2, current_timestamp, 3),
 (8, 'OPEN', 'LOW', 'Güvenlik farkındalık eğitimi içeriği', 'Q4 eğitim modüllerinin hazırlanması.',
    current_timestamp + INTERVAL 14 DAY, 6, current_timestamp, 2, current_timestamp, 2),
 (9, 'DONE', 'HIGH', 'API rate-limit bypass bulgusu', 'Pentest bulgusunun raporlanması ve retest.',
    current_timestamp + INTERVAL 3 DAY, NULL, current_timestamp, 2, current_timestamp, 4),
 (10, 'IN_PROGRESS', 'MEDIUM', 'EDR ajan kapsama raporu', 'Ajanı olmayan uç noktaların tespiti.',
    current_timestamp + INTERVAL 7 DAY, 3, current_timestamp, 2, current_timestamp, 2);

INSERT OR IGNORE INTO task_assignee (task_id, user_id) VALUES
 (1, 3), (1, 5),
 (2, 6),
 (3, 4),
 (4, 3),
 (5, 5),
 (6, 6),
 (7, 3), (7, 4),
 (8, 2),
 (9, 4),
 (10, 2), (10, 6);

INSERT OR IGNORE INTO task_history (id, task_id, action_type, action_description, action_by, action_date) VALUES
 (1, 1, 'created', 'Task oluşturuldu.', 2, current_timestamp),
 (2, 2, 'created', 'Task oluşturuldu.', 2, current_timestamp - INTERVAL 5 DAY),
 (3, 3, 'created', 'Task oluşturuldu.', 2, current_timestamp),
 (4, 4, 'created', 'Task oluşturuldu.', 2, current_timestamp),
 (5, 5, 'created', 'Task oluşturuldu.', 2, current_timestamp - INTERVAL 2 DAY),
 (6, 6, 'created', 'Task oluşturuldu.', 2, current_timestamp),
 (7, 7, 'created', 'Task oluşturuldu.', 2, current_timestamp),
 (8, 8, 'created', 'Task oluşturuldu.', 2, current_timestamp),
 (9, 9, 'created', 'Task oluşturuldu.', 2, current_timestamp),
 (10, 10, 'created', 'Task oluşturuldu.', 2, current_timestamp);

INSERT OR IGNORE INTO activity (id, activity_name, activity_description, activity_date, location, activity_type, participation_type, contact_person_id, created_by) VALUES
 (1, 'CTF Takım Antrenmanı', 'Haftalık CTF çalışması — web & pwn kategorileri.',
    date_trunc('hour', current_timestamp) + INTERVAL 2 DAY + INTERVAL 2 HOUR, 'Lab-3', 'TRAINING', 'CORPORATE', 4, 2),
 (2, 'Tehdit İstihbaratı Brifingi', 'Haftalık APT aktiviteleri değerlendirmesi.',
    date_trunc('hour', current_timestamp) + INTERVAL 4 DAY + INTERVAL 2 HOUR, 'Toplantı Odası A', 'OTHER', 'CORPORATE', 5, 2),
 (3, 'Red Team vs Blue Team Tatbikatı', 'Purple team senaryosu ile tatbikat.',
    date_trunc('hour', current_timestamp) + INTERVAL 9 DAY + INTERVAL 2 HOUR, 'SOC', 'TRAINING', 'CORPORATE', 2, 2),
 (4, 'Bulut Güvenliği Workshop', 'AWS IAM misconfiguration örnekleri.',
    date_trunc('hour', current_timestamp) + INTERVAL 14 DAY + INTERVAL 2 HOUR, 'Online', 'CONFERENCE', 'INDIVIDUAL', 6, 2),
 (5, 'Olay Müdahale Retrospektifi', 'Geçen ayki olayın lessons-learned toplantısı.',
    date_trunc('hour', current_timestamp) - INTERVAL 5 DAY + INTERVAL 2 HOUR, 'SOC', 'OTHER', 'CORPORATE', 2, 2);

INSERT OR IGNORE INTO activity_attendee (activity_id, user_id) VALUES
 (1, 3), (1, 4), (1, 5), (1, 6),
 (2, 2), (2, 3), (2, 5),
 (3, 2), (3, 3), (3, 4), (3, 5), (3, 6),
 (4, 6), (4, 4),
 (5, 2), (5, 3);

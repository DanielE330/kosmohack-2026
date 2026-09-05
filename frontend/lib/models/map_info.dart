/// Роль текущего пользователя на карте. `owner` — создатель (неявно может
/// всё), `editor`/`viewer` — права участника, которого пригласили (см.
/// `backend/app/models/map.py`). Названо не `Map`, чтобы не конфликтовать
/// с `dart:core`'s `Map<K, V>`.
enum MapRole { owner, editor, viewer }

MapRole mapRoleFromString(String value) => MapRole.values.firstWhere(
      (r) => r.name == value,
      orElse: () => MapRole.viewer,
    );

/// Может ли пользователь с этой ролью рисовать/менять/удалять полигоны.
bool mapRoleCanEdit(MapRole role) => role == MapRole.owner || role == MapRole.editor;

class MapInfo {
  final int id;
  final String name;
  final int ownerId;
  final MapRole role;

  const MapInfo({
    required this.id,
    required this.name,
    required this.ownerId,
    required this.role,
  });

  factory MapInfo.fromJson(Map<String, dynamic> json) => MapInfo(
        id: json['id'] as int,
        name: json['name'] as String,
        ownerId: json['owner_id'] as int,
        role: mapRoleFromString(json['role'] as String),
      );
}

class MapMemberInfo {
  final int userId;
  final String invitedEmail;
  final MapRole role;

  const MapMemberInfo({required this.userId, required this.invitedEmail, required this.role});

  factory MapMemberInfo.fromJson(Map<String, dynamic> json) => MapMemberInfo(
        userId: json['user_id'] as int,
        invitedEmail: json['invited_email'] as String,
        role: mapRoleFromString(json['role'] as String),
      );
}

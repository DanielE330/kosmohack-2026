/// Витринные аккаунты, которыми можно войти на демо-стенде.
///
/// Список продублирован на бэкенде (`backend/app/services/demo_seed.py`,
/// `DEMO_ACCOUNTS`) — там эти же пользователи заводятся идемпотентным
/// сидом при старте. Менять только синхронно с ним, иначе экран входа
/// будет обещать доступ, которого нет.
///
/// Тот же список подставляется в [MockAuthRepository], чтобы кнопки
/// «Подставить» работали одинаково и на моке, и на реальном бэкенде.
library;

class DemoAccount {
  const DemoAccount({
    required this.email,
    required this.password,
    required this.title,
    required this.description,
  });

  final String email;
  final String password;

  /// Роль человеческим языком — то, чем аккаунты отличаются на демо.
  final String title;

  /// Что этому аккаунту доступно: права на общей демо-карте (owner /
  /// editor / viewer, см. `MapMember` на бэкенде).
  final String description;
}

const demoAccounts = <DemoAccount>[
  DemoAccount(
    email: 'demo@skytime.dev',
    password: 'demo1234',
    title: 'Владелец',
    description: 'Своя карта участков, приглашает остальных',
  ),
  DemoAccount(
    email: 'agronom@skytime.dev',
    password: 'agronom1234',
    title: 'Агроном',
    description: 'Может рисовать и править участки на общей карте',
  ),
  DemoAccount(
    email: 'analyst@skytime.dev',
    password: 'analyst1234',
    title: 'Аналитик',
    description: 'Та же карта только для чтения: графики, отчёты',
  ),
  DemoAccount(
    email: 'viewer@skytime.dev',
    password: 'viewer1234',
    title: 'Наблюдатель',
    description: 'Только просмотр состояния участков',
  ),
];

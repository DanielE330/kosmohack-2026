/// Ошибка HTTP-вызова бэкенда с сохранённым кодом ответа. Раньше на его
/// месте был безликий `Exception('API error 404: ...')`, и экранам
/// приходилось бы разбирать текст, чтобы отличить «нет такого участка» от
/// «нужно войти» — а это разные подсказки пользователю (см.
/// `_PolygonRoute` в app.dart: по ссылке «поделиться» без входа бэкенд
/// отвечает 401, и правильная реакция — предложить войти, а не сказать
/// «Полигон не найден»).
class ApiException implements Exception {
  ApiException(this.statusCode, this.message);

  final int statusCode;

  /// `detail` из ответа FastAPI (уже по-русски), либо сырое тело.
  final String message;

  bool get isUnauthorized => statusCode == 401;
  bool get isForbidden => statusCode == 403;
  bool get isNotFound => statusCode == 404;

  @override
  String toString() => 'API error $statusCode: $message';
}

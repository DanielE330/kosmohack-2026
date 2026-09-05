import 'package:flutter/material.dart';

/// Вордмарк «sky time» — растровый логотип (`assets/logo/skytime_wordmark.png`),
/// присланный дизайнером. Раньше здесь была собственная программная
/// отрисовка (текст + нарисованная кодом дуга-орбита) — заменена на
/// реальный файл логотипа, чтобы бренд везде выглядел одинаково с тем,
/// что утверждено дизайном.
///
/// [color], если задан, перекрашивает весь логотип в один цвет (нужно на
/// тёмном AppBar — там текст должен быть светлым, а не тёмно-навигационным,
/// как в оригинальном файле) — теряется бирюзово-лаймовый акцент значка,
/// но логотип остаётся читаемым на тёмном фоне.
class SkyTimeLogo extends StatelessWidget {
  const SkyTimeLogo({super.key, this.height = 22, this.color});

  final double height;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final image = Image.asset(
      'assets/logo/skytime_wordmark.png',
      height: height,
      fit: BoxFit.contain,
    );
    if (color == null) return image;
    return ColorFiltered(
      colorFilter: ColorFilter.mode(color!, BlendMode.srcIn),
      child: image,
    );
  }
}

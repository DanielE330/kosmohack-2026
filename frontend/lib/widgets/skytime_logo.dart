import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme.dart';

/// Вордмарк «sky time» — вдохновлён референсом дизайна в `../../style/`
/// (не копия, а собственная интерпретация: точку «i» заменяет дуга-орбита
/// с двумя точками teal/lime, отсылка к спутниковому мониторингу).
///
/// Геометрия дуги/точек задана как доля от [height], а не в фиксированных
/// пикселях, и весь рисунок гарантированно укладывается в отведённый
/// прямоугольник (см. константы `_orbit*` ниже) — это важно, потому что
/// виджет используется как крошечный, ~20px, элемент в AppBar.
class SkyTimeLogo extends StatelessWidget {
  const SkyTimeLogo({super.key, this.height = 22, this.color});

  final double height;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final textColor = color ?? SkyTimeColors.navy;
    final style = TextStyle(
      fontSize: height,
      fontWeight: FontWeight.w600,
      color: textColor,
      letterSpacing: -0.3,
      height: 1,
    );
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('sky t', style: style),
        SizedBox(
          width: height * _OrbitDotPainter.orbitWidthFactor,
          height: height,
          child: CustomPaint(painter: _OrbitDotPainter(height: height)),
        ),
        Text('me', style: style),
      ],
    );
  }
}

class _OrbitDotPainter extends CustomPainter {
  const _OrbitDotPainter({required this.height});

  final double height;

  // Все размеры — доли от `height`, поэтому дуга и точки масштабируются
  // вместе с текстом и остаются одинаково заметны и на 20px (AppBar), и на
  // 24-40px (about-диалог/лендинг).
  static const orbitWidthFactor = 0.82;
  static const _radiusFactor = 0.30;
  static const _strokeFactor = 0.16;
  static const _dotRadiusFactor = 0.11;
  static const _centerXFactor = 0.38;
  // Половина угла раскрытия дуги (разрыв по центру слева, там, где обычно
  // стоит точка «i»). ~37°, что даёт дуге охват ~286° — почти полный круг
  // с открытым «ртом» слева, как на референсе.
  static const _gapHalfAngle = 0.65;

  @override
  void paint(Canvas canvas, Size size) {
    final h = size.height;
    final radius = h * _radiusFactor;
    final strokeWidth = h * _strokeFactor;
    final dotRadius = h * _dotRadiusFactor;
    final center = Offset(h * _centerXFactor, h / 2);
    final rect = Rect.fromCircle(center: center, radius: radius);

    final startAngle = math.pi + _gapHalfAngle;
    final sweepAngle = 2 * math.pi - 2 * _gapHalfAngle;
    final endAngle = startAngle + sweepAngle;

    final arcPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        startAngle: startAngle,
        endAngle: endAngle,
        colors: const [SkyTimeColors.teal, SkyTimeColors.lime],
      ).createShader(rect);
    canvas.drawArc(rect, startAngle, sweepAngle, false, arcPaint);

    final dotTop = center + Offset(math.cos(startAngle), math.sin(startAngle)) * radius;
    final dotBottom = center + Offset(math.cos(endAngle), math.sin(endAngle)) * radius;
    canvas.drawCircle(dotTop, dotRadius, Paint()..color = SkyTimeColors.teal);
    canvas.drawCircle(dotBottom, dotRadius, Paint()..color = SkyTimeColors.lime);
  }

  @override
  bool shouldRepaint(covariant _OrbitDotPainter oldDelegate) => oldDelegate.height != height;
}

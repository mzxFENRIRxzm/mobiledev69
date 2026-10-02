import 'package:flutter/material.dart';
import 'app_theme.dart';

/// Finite entrance motion; preserves the child's state on data refresh.
class Reveal extends StatelessWidget {
  final Widget child;
  final int delay;
  const Reveal({super.key, required this.child, this.delay = 0});
  @override
  Widget build(BuildContext context) {
    if (MediaQuery.disableAnimationsOf(context) ||
        MediaQuery.accessibleNavigationOf(context)) {
      return child;
    }
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 420 + delay),
      curve: Interval(delay / (420 + delay), 1, curve: Curves.easeOutCubic),
      child: child,
      builder: (_, value, child) => Opacity(
        opacity: value,
        child: Transform.translate(
          offset: Offset(0, 14 * (1 - value)),
          child: child,
        ),
      ),
    );
  }
}

class BrandMark extends StatelessWidget {
  const BrandMark({super.key});
  @override
  Widget build(BuildContext context) => const Text.rich(
    TextSpan(
      children: [
        TextSpan(
          text: 'THE_',
          style: TextStyle(color: Color(0xfff5f2ee)),
        ),
        TextSpan(
          text: 'X',
          style: TextStyle(color: AppColors.gold),
        ),
      ],
    ),
    style: TextStyle(
      fontSize: 24,
      letterSpacing: 3,
      fontWeight: FontWeight.w800,
    ),
  );
}

class SectionHeading extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget? action;
  const SectionHeading({
    super.key,
    required this.title,
    this.subtitle,
    this.action,
  });
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 18),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleLarge),
              if (subtitle != null) ...[
                const SizedBox(height: 5),
                Text(
                  subtitle!,
                  style: const TextStyle(color: AppColors.muted, height: 1.6),
                ),
              ],
            ],
          ),
        ),
        if (action != null) ...[const SizedBox(width: 8), action!],
      ],
    ),
  );
}

class FeatureCard extends StatefulWidget {
  final IconData icon;
  final String title, subtitle;
  final VoidCallback onTap;
  const FeatureCard({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });
  @override
  State<FeatureCard> createState() => _FeatureCardState();
}

class _FeatureCardState extends State<FeatureCard> {
  bool highlighted = false;
  @override
  Widget build(BuildContext context) => AnimatedContainer(
    duration:
        MediaQuery.disableAnimationsOf(context) ||
            MediaQuery.accessibleNavigationOf(context)
        ? Duration.zero
        : const Duration(milliseconds: 160),
    decoration: BoxDecoration(
      color: highlighted ? const Color(0xff26232a) : AppColors.surface,
      borderRadius: BorderRadius.circular(18),
      border: Border.all(
        color: highlighted ? AppColors.gold : AppColors.border,
      ),
    ),
    child: Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: widget.onTap,
        onHover: (value) => setState(() => highlighted = value),
        onFocusChange: (value) => setState(() => highlighted = value),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.gold.withValues(alpha: .08),
                  borderRadius: BorderRadius.circular(13),
                ),
                child: Icon(widget.icon, color: AppColors.gold, size: 24),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.title,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      widget.subtitle,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              const Icon(Icons.arrow_outward, size: 18, color: AppColors.muted),
            ],
          ),
        ),
      ),
    ),
  );
}

class RideHero extends StatelessWidget {
  final String eyebrow, title, subtitle;
  final Widget? action;
  const RideHero({
    super.key,
    required this.eyebrow,
    required this.title,
    required this.subtitle,
    this.action,
  });
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final wide = constraints.maxWidth >= 700;
      return ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: DecoratedBox(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              colors: [Color(0xff3d2026), Color(0xff241d24), Color(0xff1b1d23)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
          ),
          child: CustomPaint(
            painter: _RideLines(),
            child: Padding(
              padding: EdgeInsets.all(wide ? 36 : 24),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          eyebrow,
                          style: const TextStyle(
                            color: AppColors.gold,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            letterSpacing: .8,
                          ),
                        ),
                        const SizedBox(height: 14),
                        Text(
                          title,
                          style: wide
                              ? Theme.of(context).textTheme.headlineLarge
                              : Theme.of(context).textTheme.headlineMedium,
                        ),
                        const SizedBox(height: 12),
                        Text(
                          subtitle,
                          style: const TextStyle(
                            color: Color(0xffd1c5c8),
                            height: 1.7,
                          ),
                        ),
                        if (action != null) ...[
                          const SizedBox(height: 24),
                          action!,
                        ],
                      ],
                    ),
                  ),
                  if (wide) ...[
                    const SizedBox(width: 32),
                    ExcludeSemantics(
                      child: Container(
                        width: 180,
                        height: 180,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: AppColors.gold.withValues(alpha: .2),
                          ),
                        ),
                        child: Center(
                          child: Container(
                            width: 142,
                            height: 142,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: AppColors.gold.withValues(alpha: .04),
                              border: Border.all(
                                color: AppColors.gold.withValues(alpha: .12),
                              ),
                            ),
                            child: const Icon(
                              Icons.two_wheeler,
                              size: 80,
                              color: AppColors.gold,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      );
    },
  );
}

class _RideLines extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppColors.gold.withValues(alpha: .045)
      ..strokeWidth = 1;
    for (double x = size.width * .5; x < size.width + size.height; x += 38) {
      canvas.drawLine(
        Offset(x, 0),
        Offset(x - size.height * .5, size.height),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_RideLines oldDelegate) => false;
}

class EmptyPanel extends StatelessWidget {
  final IconData icon;
  final String title, subtitle;
  const EmptyPanel({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
  });
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 28),
    child: Column(
      children: [
        Icon(icon, size: 38, color: AppColors.gold),
        const SizedBox(height: 16),
        Text(
          title,
          style: Theme.of(context).textTheme.titleMedium,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 6),
        Text(
          subtitle,
          style: Theme.of(context).textTheme.bodySmall,
          textAlign: TextAlign.center,
        ),
      ],
    ),
  );
}

import 'package:flutter/material.dart';

abstract final class AppColors {
  static const background = Color(0xff111216);
  static const surface = Color(0xff1b1d23);
  static const border = Color(0xff343640);
  static const gold = Color(0xffe9bd79);
  static const red = Color(0xffca4545);
  static const muted = Color(0xffb4b5bf);
}

ThemeData buildAppTheme() {
  final scheme =
      ColorScheme.fromSeed(
        seedColor: AppColors.red,
        brightness: Brightness.dark,
      ).copyWith(
        primary: AppColors.red,
        onPrimary: Colors.white,
        primaryContainer: const Color(0xff422629),
        onPrimaryContainer: const Color(0xffffd9d6),
        secondary: AppColors.gold,
        onSecondary: const Color(0xff241c11),
        surface: AppColors.surface,
        onSurface: const Color(0xfff5f2ee),
        onSurfaceVariant: AppColors.muted,
        outline: const Color(0xff777984),
        outlineVariant: AppColors.border,
      );
  final base = ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    fontFamily: 'NotoSansThai',
    scaffoldBackgroundColor: AppColors.background,
  );
  final rounded = RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(14),
  );
  return base.copyWith(
    textTheme: base.textTheme
        .copyWith(
          headlineLarge: const TextStyle(
            fontSize: 36,
            fontWeight: FontWeight.w700,
            height: 1.4,
          ),
          headlineMedium: const TextStyle(
            fontSize: 28,
            fontWeight: FontWeight.w700,
            height: 1.45,
          ),
          titleLarge: const TextStyle(
            fontSize: 21,
            fontWeight: FontWeight.w700,
            height: 1.5,
          ),
          titleMedium: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            height: 1.55,
          ),
          bodyLarge: const TextStyle(fontSize: 16, height: 1.65),
          bodyMedium: const TextStyle(fontSize: 14, height: 1.65),
          bodySmall: const TextStyle(
            fontSize: 12,
            height: 1.6,
            color: AppColors.muted,
          ),
        )
        .apply(
          fontFamily: 'NotoSansThai',
          bodyColor: scheme.onSurface,
          displayColor: scheme.onSurface,
        )
        .copyWith(
          bodySmall: const TextStyle(
            fontFamily: 'NotoSansThai',
            fontSize: 12,
            height: 1.6,
            color: AppColors.muted,
          ),
        ),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.background,
      foregroundColor: Color(0xfff5f2ee),
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      toolbarHeight: 76,
      titleSpacing: 24,
      shape: Border(bottom: BorderSide(color: AppColors.border)),
    ),
    cardTheme: CardThemeData(
      color: AppColors.surface,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      margin: const EdgeInsets.symmetric(vertical: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: AppColors.border),
      ),
      clipBehavior: Clip.antiAlias,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: const Color(0xff15171c),
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
      hintStyle: const TextStyle(color: AppColors.muted, fontSize: 14),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.gold, width: 2),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(48, 50),
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
        textStyle: const TextStyle(
          fontFamily: 'NotoSansThai',
          fontWeight: FontWeight.w600,
          fontSize: 14,
        ),
        shape: rounded,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: scheme.onSurface,
        minimumSize: const Size(48, 50),
        side: const BorderSide(color: AppColors.border),
        shape: rounded,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: AppColors.gold,
        minimumSize: const Size(48, 48),
        shape: rounded,
      ),
    ),
    iconButtonTheme: IconButtonThemeData(
      style: IconButton.styleFrom(
        minimumSize: const Size(48, 48),
        foregroundColor: scheme.onSurfaceVariant,
      ),
    ),
    dividerTheme: const DividerThemeData(color: AppColors.border, space: 24),
    dialogTheme: DialogThemeData(
      backgroundColor: AppColors.surface,
      shape: rounded,
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: rounded,
    ),
    popupMenuTheme: PopupMenuThemeData(
      color: AppColors.surface,
      shape: rounded,
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: AppColors.gold,
    ),
    pageTransitionsTheme: const PageTransitionsTheme(
      builders: {
        TargetPlatform.android: _SoftPageTransition(),
        TargetPlatform.iOS: _SoftPageTransition(),
        TargetPlatform.windows: _SoftPageTransition(),
        TargetPlatform.macOS: _SoftPageTransition(),
        TargetPlatform.linux: _SoftPageTransition(),
        TargetPlatform.fuchsia: _SoftPageTransition(),
      },
    ),
  );
}

class _SoftPageTransition extends PageTransitionsBuilder {
  const _SoftPageTransition();
  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) {
    if (MediaQuery.disableAnimationsOf(context) ||
        MediaQuery.accessibleNavigationOf(context)) {
      return child;
    }
    return FadeTransition(
      opacity: animation.drive(CurveTween(curve: Curves.easeOut)),
      child: child,
    );
  }
}

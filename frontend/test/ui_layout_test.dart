import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:the_x/core/api/api_service.dart';
import 'package:the_x/core/ui/app_theme.dart';
import 'package:the_x/core/ui/app_widgets.dart';
import 'package:the_x/features/auth/auth_repository.dart';
import 'package:the_x/features/auth/auth_view_model.dart';
import 'package:the_x/features/auth/login_screen.dart';
import 'package:the_x/features/garage/data/garage_repository.dart';
import 'package:the_x/features/garage/domain/motorcycle.dart';
import 'package:the_x/features/garage/presentation/garage_screen.dart';
import 'package:the_x/features/garage/presentation/garage_view_model.dart';
import 'ai_chat_test.dart' show FakeAiApi;

class _OverviewApi extends FakeAiApi {
  @override
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Object? data,
  }) async => {'results': <dynamic>[], 'next': null};
}

void main() {
  test('headings and body text define readable colors on the dark canvas', () {
    final theme = buildAppTheme();
    final background = theme.scaffoldBackgroundColor.computeLuminance();
    for (final style in [
      theme.textTheme.headlineLarge,
      theme.textTheme.headlineMedium,
      theme.textTheme.titleLarge,
      theme.textTheme.titleMedium,
      theme.textTheme.bodyLarge,
      theme.textTheme.bodyMedium,
      theme.textTheme.bodySmall,
    ]) {
      expect(style!.color, isNotNull);
      expect(
        (style.color!.computeLuminance() + .05) / (background + .05),
        greaterThan(4.5),
      );
    }
  });
  for (final width in [360.0, 1440.0]) {
    testWidgets('login and garage fit $width px and large text', (
      tester,
    ) async {
      tester.view.physicalSize = Size(width, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.runAsync(() async {
        final font = FontLoader('NotoSansThai')
          ..addFont(rootBundle.load('assets/fonts/NotoSansThai.ttf'));
        await font.load();
        final icons = FontLoader('MaterialIcons')
          ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
        await icons.load();
      });
      final api = _OverviewApi();
      final auth = AuthViewModel(AuthRepository(api.auth, api))
        ..user = const AppUser('Rider', 'customer')
        ..loading = false;
      final garage = GarageViewModel(GarageRepository(api))
        ..motorcycles = [
          const Motorcycle(
            id: 1,
            brand: 'Honda',
            model: 'CB650R',
            plate: 'TEST',
            year: 2025,
            mileage: 3200,
          ),
        ];
      addTearDown(auth.dispose);
      addTearDown(garage.dispose);
      final boundary = GlobalKey();
      Future<void> mount(Widget child, double scale) async {
        await tester.pumpWidget(
          MultiProvider(
            providers: [
              Provider<ApiService>.value(value: api),
              ChangeNotifierProvider<AuthViewModel>.value(value: auth),
              ChangeNotifierProvider<GarageViewModel>.value(value: garage),
            ],
            child: MaterialApp(
              theme: buildAppTheme(),
              home: RepaintBoundary(key: boundary, child: child),
              builder: (context, child) => MediaQuery(
                data: MediaQuery.of(
                  context,
                ).copyWith(textScaler: TextScaler.linear(scale)),
                child: child!,
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      }

      Future<void> capture(String name) async {
        if (!const bool.fromEnvironment('UI_PREVIEWS')) return;
        final render =
            boundary.currentContext!.findRenderObject()!
                as RenderRepaintBoundary;
        await tester.runAsync(() async {
          final image = await render.toImage();
          final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
          final file = File('../.local/$name-${width.toInt()}.png');
          await file.parent.create(recursive: true);
          await file.writeAsBytes(bytes!.buffer.asUint8List());
          image.dispose();
        });
      }

      await mount(const LoginScreen(), 1);
      await capture('login');
      await mount(const LoginScreen(), 1.8);
      await mount(const GarageScreen(), 1);
      await capture('garage');
      await mount(const GarageScreen(), 1.8);
      // The vehicle section remains reachable below the responsive overview.
      await tester.scrollUntilVisible(
        find.text('เพิ่มรถของฉัน'),
        350,
        scrollable: find.byType(Scrollable).first,
        maxScrolls: 30,
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('เพิ่มรถของฉัน'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
    });
  }
  testWidgets(
    'reduced motion exposes content immediately and creates no animation',
    (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: MediaQuery(
            data: MediaQueryData(disableAnimations: true),
            child: Scaffold(body: Reveal(delay: 120, child: Text('Ready'))),
          ),
        ),
      );
      expect(find.text('Ready'), findsOneWidget);
      expect(find.byType(TweenAnimationBuilder<double>), findsNothing);
      expect(tester.binding.transientCallbackCount, 0);
    },
  );
}

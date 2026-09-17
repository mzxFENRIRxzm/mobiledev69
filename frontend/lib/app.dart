import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'core/api/api_service.dart';
import 'core/auth/auth_service.dart';
import 'features/auth/auth_repository.dart';
import 'features/auth/auth_view_model.dart';
import 'features/auth/login_screen.dart';
import 'features/auth/admin_screen.dart';
import 'features/garage/data/garage_repository.dart';
import 'features/garage/presentation/garage_screen.dart';
import 'features/garage/presentation/garage_view_model.dart';
import 'features/bookings/data/booking_repository.dart';
import 'features/bookings/presentation/booking_screen.dart';
import 'features/bookings/presentation/booking_view_model.dart';
import 'features/shops/data/shop_repository.dart';
import 'features/shops/presentation/shop_screen.dart';
import 'features/shops/presentation/shop_view_model.dart';

class TheXApp extends StatefulWidget {
  const TheXApp({super.key});
  @override
  State<TheXApp> createState() => _TheXAppState();
}

class _TheXAppState extends State<TheXApp> {
  late final AuthService authService;
  late final ApiService api;
  late final AuthViewModel auth;
  late final GoRouter router;
  @override
  void initState() {
    super.initState();
    authService = AuthService(const FlutterSecureStorage());
    api = ApiService(authService);
    auth = AuthViewModel(AuthRepository(authService, api));
    router = GoRouter(
      refreshListenable: auth,
      redirect: (context, state) {
        if (auth.loading) {
          return state.matchedLocation == '/loading' ? null : '/loading';
        }
        if (auth.username == null) {
          return state.matchedLocation == '/login' ? null : '/login';
        }
        if (auth.isAdmin) {
          return state.matchedLocation == '/admin' ? null : '/admin';
        }
        if (state.matchedLocation == '/admin') {
          return auth.isMechanic ? '/jobs' : '/garage';
        }
        if ([
          '/login',
          '/loading',
          '/callback',
          '/',
        ].contains(state.matchedLocation)) {
          return auth.isMechanic ? '/jobs' : '/garage';
        }
        if (auth.isMechanic &&
            ['/garage', '/bookings'].contains(state.matchedLocation)) {
          return '/jobs';
        }
        if (!auth.isMechanic && state.matchedLocation == '/jobs') {
          return '/bookings';
        }
        return null;
      },
      routes: [
        GoRoute(path: '/admin', builder: (_, _) => const AdminScreen()),
        GoRoute(
          path: '/shops',
          builder: (_, _) => ChangeNotifierProvider(
            create: (_) => ShopViewModel(ShopRepository(api))..load(),
            child: const ShopScreen(),
          ),
        ),
        for (final path in ['/bookings', '/jobs'])
          GoRoute(
            path: path,
            builder: (_, state) => ChangeNotifierProvider(
              create: (_) => BookingViewModel(BookingRepository(api))..load(),
              child: BookingScreen(
                initialShop: int.tryParse(
                  state.uri.queryParameters['shop'] ?? '',
                ),
              ),
            ),
          ),
        GoRoute(path: '/', builder: (_, _) => const SizedBox()),
        GoRoute(path: '/callback', builder: (_, _) => const SizedBox()),
        GoRoute(
          path: '/loading',
          builder: (_, _) =>
              const Scaffold(body: Center(child: CircularProgressIndicator())),
        ),
        GoRoute(path: '/login', builder: (_, _) => const LoginScreen()),
        GoRoute(
          path: '/garage',
          builder: (_, _) => ChangeNotifierProvider(
            create: (_) => GarageViewModel(GarageRepository(api))..load(),
            child: const GarageScreen(),
          ),
        ),
      ],
    );
    auth.restore(Uri.base);
  }

  @override
  void dispose() {
    router.dispose();
    auth.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MultiProvider(
    providers: [
      Provider.value(value: api),
      ChangeNotifierProvider.value(value: auth),
    ],
    child: MaterialApp.router(
      title: 'THE_X · Your ride, cared for',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xffc7f36b),
          brightness: Brightness.dark,
          primary: const Color(0xffc7f36b),
          surface: const Color(0xff151e20),
        ),
        scaffoldBackgroundColor: const Color(0xff101719),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
          filled: true,
        ),
        appBarTheme: const AppBarTheme(backgroundColor: Color(0xff101719)),
      ),
      routerConfig: router,
    ),
  );
}

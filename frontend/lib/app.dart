import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'core/api/api_service.dart';
import 'core/auth/auth_service.dart';
import 'core/auth/auth_storage.dart';
import 'core/auth/return_path.dart';
import 'core/ui/app_theme.dart';
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
import 'features/profile/profile_repository.dart';
import 'features/profile/profile_view_model.dart';
import 'features/profile/profile_screen.dart';
import 'features/chat/chat_screen.dart';
import 'features/notifications/notification_store.dart';

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
  late final NotificationStore notifications;
  String? returnPath;
  Future<void> _restore(AuthStorage storage) async {
    final location = Uri.base;
    returnPath = safeReturnPath(
      location.path + (location.hasQuery ? '?${location.query}' : ''),
    );
    if (location.path == '/callback') {
      returnPath = safeReturnPath(await storage.read(key: 'return_path'));
    }
    if (returnPath != null) {
      await storage.write(key: 'return_path', value: returnPath);
    }
    await auth.restore(location);
    if (auth.username != null || location.path == '/login') {
      await storage.delete(key: 'return_path');
    }
  }

  void _syncNotifications() => notifications.setAccount(
    auth.user == null ? null : '${auth.username}:${auth.user!.role}',
  );
  @override
  void initState() {
    super.initState();
    // Keep OIDC credentials and PKCE state in the current browser tab.
    final storage = createAuthStorage();
    authService = AuthService.withStorage(storage);
    api = ApiService(authService);
    auth = AuthViewModel(AuthRepository(authService, api));
    notifications = NotificationStore(api);
    auth.addListener(_syncNotifications);
    router = GoRouter(
      refreshListenable: auth,
      redirect: (context, state) {
        if (auth.loading) {
          if (state.matchedLocation == '/loading') return null;
          return '/loading';
        }
        if (auth.username == null) {
          return state.matchedLocation == '/login' ? null : '/login';
        }
        if (returnPath != null) {
          final target = returnPath!;
          returnPath = null;
          if (state.uri.toString() != target) return target;
        }
        if (auth.isAdmin) {
          return state.matchedLocation == '/admin-dashboard' ? null : '/admin-dashboard';
        }
        if (state.matchedLocation == '/admin-dashboard') {
          return auth.isMechanic ? '/jobs' : '/garage';
        }
        if (state.matchedLocation == '/loading' &&
            state.uri.queryParameters['next'] == 'profile') {
          return '/profile';
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
            [
              '/garage',
              '/bookings',
              '/ai-chat',
            ].contains(state.matchedLocation)) {
          return '/jobs';
        }
        if (!auth.isMechanic && state.matchedLocation == '/jobs') {
          return '/bookings';
        }
        return null;
      },
      routes: [
        GoRoute(
          path: '/profile',
          builder: (_, _) => ChangeNotifierProvider(
            create: (_) => ProfileViewModel(ProfileRepository(api))..load(),
            child: const ProfileScreen(),
          ),
        ),
        GoRoute(path: '/admin-dashboard', builder: (_, _) => const AdminScreen()),
        GoRoute(
          path: '/messages',
          builder: (_, state) => MessagesScreen(
            key: ValueKey(state.uri.toString()),
            initialShop: int.tryParse(state.uri.queryParameters['shop'] ?? ''),
            initialConversation: int.tryParse(
              state.uri.queryParameters['conversation'] ?? '',
            ),
          ),
        ),
        GoRoute(path: '/ai-chat', builder: (_, _) => const AiChatScreen()),
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
    _restore(storage);
  }

  @override
  void dispose() {
    router.dispose();
    auth.removeListener(_syncNotifications);
    notifications.dispose();
    auth.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MultiProvider(
    providers: [
      Provider.value(value: api),
      ChangeNotifierProvider.value(value: auth),
      ChangeNotifierProvider.value(value: notifications),
    ],
    child: MaterialApp.router(
      title: 'THE_X · Your ride, cared for',
      debugShowCheckedModeBanner: false,
      theme: buildAppTheme(),
      routerConfig: router,
    ),
  );
}

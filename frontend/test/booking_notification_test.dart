import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:the_x/features/bookings/data/booking_repository.dart';
import 'package:the_x/features/bookings/presentation/booking_view_model.dart';
import 'package:the_x/features/notifications/notification_bell.dart';
import 'package:the_x/features/notifications/notification_store.dart';
import 'ai_chat_test.dart' show FakeAiApi;

class BookingNotificationApi extends FakeAiApi {
  int bookingLoads = 0;
  @override
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Object? data,
  }) async {
    if (path.startsWith('bookings/')) {
      bookingLoads++;
      return {'results': [], 'next': null};
    }
    return {'ok': true};
  }
}

void main() {
  testWidgets(
    'opening a booking notification refreshes the current booking page',
    (tester) async {
      final api = BookingNotificationApi();
      final bookings = BookingViewModel(BookingRepository(api));
      final inbox = NotificationStore(api)
        ..items = [
          {'id': 1, 'title': 'Booking started', 'booking': 2},
        ];
      final router = GoRouter(
        initialLocation: '/bookings',
        routes: [
          GoRoute(
            path: '/bookings',
            builder: (_, _) => ChangeNotifierProvider.value(
              value: bookings,
              child: const Scaffold(body: NotificationBell()),
            ),
          ),
        ],
      );
      await tester.pumpWidget(
        ChangeNotifierProvider.value(
          value: inbox,
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byType(IconButton));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Booking started'));
      await tester.pumpAndSettle();
      expect(api.bookingLoads, 1);
      expect(router.routeInformationProvider.value.uri.path, '/bookings');
      expect(find.text('Booking started'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      router.dispose();
      bookings.dispose();
      inbox.dispose();
    },
  );
}

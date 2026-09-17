import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:the_x/features/auth/auth_repository.dart';
import 'package:the_x/features/auth/auth_view_model.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:the_x/core/api/api_service.dart';
import 'package:the_x/core/auth/auth_service.dart';
import 'package:the_x/core/result.dart';
import 'package:the_x/features/bookings/data/booking_repository.dart';
import 'package:the_x/features/bookings/domain/booking.dart';
import 'package:the_x/features/bookings/presentation/booking_screen.dart';
import 'package:the_x/features/bookings/presentation/booking_view_model.dart';

class FakeBookings extends BookingRepository {
  FakeBookings() : super(ApiService(AuthService(const FlutterSecureStorage())));
  int writes = 0;
  Completer<Result<void>>? pending;
  @override
  Future<Result<List<Booking>>> list() async => const Success([]);
  @override
  Future<Result<void>> transition(int id, String action, String notes) {
    writes++;
    return pending?.future ??
        Future.value(const Failure('สถานะงานเปลี่ยนแล้ว กรุณาโหลดใหม่'));
  }
}

class WorkflowBookings extends FakeBookings {
  String status = 'pending';
  @override
  Future<Result<List<Booking>>> list() async => Success([
    Booking.fromJson({
      'id': 42,
      'motorcycle_label': 'Test bike',
      'customer_name': 'customer',
      'mechanic_name': status == 'pending' ? null : 'mechanic',
      'status': status,
      'problem': 'noise',
      'repair_notes': '',
      'appointment_at': '2027-01-01T09:00:00Z',
      'events': [],
    }),
  ]);
  @override
  Future<Result<void>> transition(int id, String action, String notes) async {
    status = 'accepted';
    return const Success(null);
  }
}

void main() {
  testWidgets('expanded booking stays open after accept and reload', (
    tester,
  ) async {
    final service = AuthService(const FlutterSecureStorage());
    final auth = AuthViewModel(AuthRepository(service, ApiService(service)))
      ..user = const AppUser('mechanic', 'mechanic')
      ..loading = false;
    final vm = BookingViewModel(WorkflowBookings());
    await vm.load();
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: auth),
          ChangeNotifierProvider.value(value: vm),
        ],
        child: const MaterialApp(home: BookingScreen()),
      ),
    );
    await tester.tap(find.text('#42 · Test bike'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('รับงาน'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('ยืนยัน'));
    await tester.pumpAndSettle();
    expect(find.text('เริ่มซ่อม'), findsOneWidget);
    vm.dispose();
    auth.dispose();
  });
  test('blocks duplicate submission while a transition is pending', () async {
    final repo = FakeBookings()..pending = Completer<Result<void>>();
    final vm = BookingViewModel(repo);
    final first = vm.transition(1, 'accept', '');
    expect(await vm.transition(1, 'accept', ''), isNotNull);
    expect(repo.writes, 1);
    repo.pending!.complete(const Success(null));
    expect(await first, isNull);
    expect(vm.busy, isFalse);
    vm.dispose();
  });
  testWidgets(
    'completion requires notes and preserves notes on server rejection',
    (tester) async {
      final repo = FakeBookings();
      final vm = BookingViewModel(repo);
      final booking = Booking.fromJson({
        'id': 1,
        'motorcycle_label': 'Honda PCX',
        'customer_name': 'customer',
        'mechanic_name': 'mechanic',
        'status': 'in_progress',
        'problem': 'noise',
        'repair_notes': '',
        'appointment_at': '2026-09-20T09:00:00Z',
        'events': [],
      });
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: TransitionDialog(
              vm: vm,
              booking: booking,
              action: 'complete',
              label: 'ปิดงานซ่อม',
            ),
          ),
        ),
      );
      await tester.tap(find.text('ยืนยัน'));
      await tester.pump();
      expect(repo.writes, 0);
      expect(find.text('กรุณาระบุรายละเอียดงานซ่อม'), findsOneWidget);
      await tester.enterText(find.byType(TextField), 'เปลี่ยนน้ำมันเครื่อง');
      await tester.tap(find.text('ยืนยัน'));
      await tester.pumpAndSettle();
      expect(repo.writes, 1);
      expect(find.text('เปลี่ยนน้ำมันเครื่อง'), findsOneWidget);
      expect(find.text('สถานะงานเปลี่ยนแล้ว กรุณาโหลดใหม่'), findsOneWidget);
      vm.dispose();
    },
  );
}

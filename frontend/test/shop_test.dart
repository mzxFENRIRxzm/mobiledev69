import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:the_x/core/api/api_service.dart';
import 'package:the_x/core/auth/auth_service.dart';
import 'package:the_x/core/result.dart';
import 'package:the_x/features/shops/domain/shop.dart';
import 'package:the_x/features/shops/data/shop_repository.dart';
import 'package:the_x/features/shops/presentation/shop_screen.dart';
import 'package:the_x/features/shops/presentation/shop_view_model.dart';
import 'package:the_x/features/bookings/data/booking_repository.dart';
import 'package:the_x/features/bookings/presentation/booking_screen.dart';
import 'package:the_x/features/bookings/presentation/booking_view_model.dart';
import 'package:the_x/features/garage/data/garage_repository.dart';
import 'package:the_x/features/garage/domain/motorcycle.dart';

final api = ApiService(AuthService(const FlutterSecureStorage()));
Shop shop(int id, bool open) => Shop.fromJson({
  'id': id,
  'name': 'Shop $id',
  'address': 'Bangkok',
  'phone': 'contact',
  'description': '',
  'accepting_bookings': open,
  'can_manage': true,
});

class FakeShops extends ShopRepository {
  FakeShops() : super(api);
  int writes = 0;
  @override
  Future<Result<List<Shop>>> list() async =>
      Success([shop(1, true), shop(2, false)]);
  @override
  Future<Result<void>> save(int id, Map<String, dynamic> data) async {
    writes++;
    return const Failure('ไม่มีสิทธิ์แก้ไขร้านนี้');
  }
}

class FakeGarage extends GarageRepository {
  FakeGarage() : super(api);
  @override
  Future<Result<List<Motorcycle>>> list() async => const Success([
    Motorcycle(
      id: 1,
      brand: 'Honda',
      model: 'PCX',
      plate: 'test',
      year: 2024,
      mileage: 0,
    ),
  ]);
}

class CapturingApi extends ApiService {
  CapturingApi() : super(AuthService(const FlutterSecureStorage()));
  Object? sent;
  @override
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Object? data,
  }) async {
    sent = data;
    return {};
  }
}

void main() {
  testWidgets('shop edit validates and keeps edited values on denial', (
    tester,
  ) async {
    final repo = FakeShops();
    final vm = ShopViewModel(repo);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ShopForm(shop: shop(1, true), vm: vm),
        ),
      ),
    );
    await tester.enterText(find.byType(TextFormField).first, '');
    await tester.tap(find.text('บันทึก'));
    await tester.pump();
    expect(repo.writes, 0);
    await tester.enterText(find.byType(TextFormField).first, 'Updated shop');
    await tester.tap(find.text('บันทึก'));
    await tester.pumpAndSettle();
    expect(repo.writes, 1);
    expect(find.text('Updated shop'), findsOneWidget);
    expect(find.text('ไม่มีสิทธิ์แก้ไขร้านนี้'), findsOneWidget);
    vm.dispose();
  });
  testWidgets('booking form preselects chosen shop and excludes closed shops', (
    tester,
  ) async {
    final vm = BookingViewModel(BookingRepository(api));
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: BookingForm(
            vm: vm,
            garage: FakeGarage(),
            shops: FakeShops(),
            initialShop: 1,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final dropdown = tester.widget<DropdownButtonFormField<int>>(
      find.byType(DropdownButtonFormField<int>).first,
    );
    expect(dropdown.initialValue, 1);
    await tester.tap(find.text('Shop 1').first);
    await tester.pumpAndSettle();
    expect(find.text('Shop 2'), findsNothing);
    vm.dispose();
  });
  test('booking sends selected shop and cancellation reason to API', () async {
    final capture = CapturingApi();
    final repo = BookingRepository(capture);
    await repo.create(1, DateTime(2027), 'noise', 9);
    expect((capture.sent as Map)['shop'], 9);
    await repo.transition(1, 'cancel', ' parts unavailable ');
    expect((capture.sent as Map)['cancellation_reason'], 'parts unavailable');
    expect((capture.sent as Map)['repair_notes'], '');
  });
}

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:the_x/core/api/api_service.dart';
import 'package:the_x/core/auth/auth_service.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:the_x/core/result.dart';
import 'package:the_x/features/garage/data/garage_repository.dart';
import 'package:the_x/features/garage/domain/motorcycle.dart';
import 'package:the_x/features/garage/presentation/garage_screen.dart';
import 'package:the_x/features/garage/presentation/garage_view_model.dart';

class FakeGarage extends GarageRepository {
  FakeGarage() : super(ApiService(AuthService(const FlutterSecureStorage())));
  int saves = 0;
  @override
  Future<Result<void>> save(Map<String, dynamic> data, {int? id}) async {
    saves++;
    return const Failure('เซิร์ฟเวอร์ไม่พร้อม กรุณาลองใหม่');
  }
}

void main() {
  test('search matches model and plate without changing source data', () {
    final vm = GarageViewModel(FakeGarage());
    vm.motorcycles = [
      const Motorcycle(
        id: 1,
        brand: 'Honda',
        model: 'PCX',
        plate: 'AB12',
        year: 2024,
        mileage: 0,
      ),
    ];
    vm.search('pcx');
    expect(vm.filtered.length, 1);
    vm.search('missing');
    expect(vm.filtered, isEmpty);
    expect(vm.motorcycles.length, 1);
  });
  testWidgets(
    'invalid form never saves; failed save preserves entered fields',
    (tester) async {
      final repo = FakeGarage();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: MotorcycleForm(vm: GarageViewModel(repo))),
        ),
      );
      await tester.tap(find.text('บันทึก'));
      await tester.pump();
      expect(repo.saves, 0);
      await tester.enterText(find.byType(TextFormField).at(0), 'Honda');
      await tester.enterText(find.byType(TextFormField).at(1), 'PCX');
      await tester.enterText(find.byType(TextFormField).at(2), 'AB12');
      await tester.tap(find.text('บันทึก'));
      await tester.pumpAndSettle();
      expect(repo.saves, 1);
      expect(find.text('เซิร์ฟเวอร์ไม่พร้อม กรุณาลองใหม่'), findsOneWidget);
      expect(find.text('Honda'), findsOneWidget);
    },
  );
}

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:the_x/features/shops/domain/shop.dart';
import 'package:the_x/features/shops/presentation/shop_map.dart';

Shop _shop({double? latitude, double? longitude}) => Shop.fromJson({
  'id': 1,
  'name': 'ร้านทดสอบ',
  'address': 'กรุงเทพฯ',
  'phone': '000',
  'description': '',
  'accepting_bookings': true,
  'can_manage': false,
  'latitude': latitude,
  'longitude': longitude,
});

void main() {
  testWidgets('map explains when no shop has a pin', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: ShopMap(shops: [_shop()])),
      ),
    );
    expect(find.text('ยังไม่มีร้านที่ปักหมุดบนแผนที่'), findsOneWidget);
  });

  testWidgets('map marks a shop with coordinates', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ShopMap(shops: [_shop(latitude: 13.75, longitude: 100.5)]),
        ),
      ),
    );
    await tester.pump();
    expect(find.byTooltip('ร้านทดสอบ'), findsOneWidget);
  });
}

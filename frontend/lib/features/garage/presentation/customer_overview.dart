import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../../../core/api/api_service.dart';
import '../../../core/result.dart';
import '../../bookings/data/booking_repository.dart';
import '../../bookings/domain/booking.dart';
import '../../shops/data/shop_repository.dart';
import '../../shops/domain/shop.dart';
import '../../shops/presentation/shop_map.dart';

class CustomerOverview extends StatefulWidget {
  const CustomerOverview({super.key});
  @override
  State<CustomerOverview> createState() => _CustomerOverviewState();
}

class _CustomerOverviewState extends State<CustomerOverview> {
  List<Booking> bookings = [];
  List<Shop> shops = [];
  String? error;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final api = context.read<ApiService>();
    final results = await Future.wait<Object>([
      BookingRepository(api).list(),
      ShopRepository(api).list(),
    ]);
    if (!mounted) return;
    final bookingResult = results[0];
    final shopResult = results[1];
    setState(() {
      loading = false;
      if (bookingResult is Success<List<Booking>>) {
        bookings = bookingResult.value;
      }
      if (shopResult is Success<List<Shop>>) shops = shopResult.value;
      error = bookingResult is Failure<List<Booking>>
          ? bookingResult.message
          : shopResult is Failure<List<Shop>>
          ? shopResult.message
          : null;
    });
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        children: [
          const Expanded(
            child: Text(
              'ภาพรวมการจอง',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
            ),
          ),
          IconButton(
            onPressed: _load,
            tooltip: 'โหลดภาพรวมใหม่',
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      if (loading) const LinearProgressIndicator(),
      if (error != null)
        Text(
          error!,
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
      if (!loading && bookings.isEmpty) const Text('ยังไม่มีรายการจองซ่อม'),
      for (final booking in bookings.take(3))
        Card(
          child: ListTile(
            title: Text('${booking.shopName} · ${booking.motorcycle}'),
            subtitle: Text(
              '${bookingStatuses[booking.status]} · ${bookingTime(booking.appointment)}',
            ),
            onTap: () => context.go('/bookings'),
          ),
        ),
      TextButton(
        onPressed: () => context.go('/bookings'),
        child: const Text('ดูรายการจองทั้งหมด'),
      ),
      const SizedBox(height: 20),
      if (!loading) ShopMap(shops: shops),
      const SizedBox(height: 30),
    ],
  );
}

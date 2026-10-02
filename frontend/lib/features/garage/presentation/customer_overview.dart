import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../../../core/api/api_service.dart';
import '../../../core/result.dart';
import '../../../core/ui/app_widgets.dart';
import '../../../core/ui/app_theme.dart';
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
    if (!mounted) return;
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
  Widget build(BuildContext context) {
    final upcoming =
        bookings
            .where(
              (b) => ['pending', 'accepted', 'in_progress'].contains(b.status),
            )
            .toList()
          ..sort((a, b) => a.appointment.compareTo(b.appointment));
    final appointments = Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SectionHeading(
              title: 'นัดหมายของคุณ',
              subtitle: loading
                  ? 'กำลังโหลดข้อมูล…'
                  : '${upcoming.length} รายการที่กำลังดำเนินการ',
              action: IconButton(
                onPressed: loading ? null : _load,
                tooltip: 'โหลดภาพรวมใหม่',
                icon: const Icon(Icons.refresh, size: 20),
              ),
            ),
            if (loading) const LinearProgressIndicator(),
            if (error != null)
              Text(
                error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            if (!loading && error == null && upcoming.isEmpty)
              const EmptyPanel(
                icon: Icons.event_available_outlined,
                title: 'ยังไม่มีนัดหมายที่กำลังดำเนินการ',
                subtitle: 'เมื่อจองกับร้าน รายการนัดหมายจะปรากฏที่นี่',
              ),
            for (final booking in upcoming.take(3))
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppColors.gold.withValues(alpha: .08),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(
                      Icons.build_outlined,
                      color: AppColors.gold,
                      size: 22,
                    ),
                  ),
                  title: Text(
                    booking.shopName,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  subtitle: Text(
                    '${booking.motorcycle}\n${bookingStatuses[booking.status]} · ${bookingTime(booking.appointment)}',
                  ),
                  onTap: () => context.go('/bookings'),
                ),
              ),
            const Divider(),
            TextButton.icon(
              onPressed: () => context.go('/bookings'),
              icon: const Icon(Icons.arrow_forward, size: 18),
              label: const Text('ดูรายการจองทั้งหมด'),
            ),
          ],
        ),
      ),
    );
    final map = Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (loading)
              const EmptyPanel(
                icon: Icons.map_outlined,
                title: 'กำลังโหลดร้านบริการ',
                subtitle: 'เตรียมตำแหน่งร้านบนแผนที่',
              )
            else if (shops.every(
              (s) => s.latitude == null || s.longitude == null,
            ))
              const EmptyPanel(
                icon: Icons.map_outlined,
                title: 'ร้านบริการบนแผนที่',
                subtitle:
                    'ร้านที่เพิ่มตำแหน่งแล้วจะแสดงที่นี่ คุณยังค้นหาร้านจากรายการได้',
              )
            else
              ShopMap(shops: shops),
            const SizedBox(height: 12),
            TextButton.icon(
              onPressed: () => context.go('/shops'),
              icon: const Icon(Icons.storefront_outlined, size: 18),
              label: const Text('ดูร้านบริการทั้งหมด'),
            ),
          ],
        ),
      ),
    );
    return Padding(
      padding: const EdgeInsets.only(bottom: 28),
      child: LayoutBuilder(
        builder: (context, size) =>
            size.maxWidth >= 900 &&
                MediaQuery.textScalerOf(context).scale(14) <= 18
            ? Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 4, child: appointments),
                  const SizedBox(width: 20),
                  Expanded(flex: 6, child: map),
                ],
              )
            : Column(children: [appointments, const SizedBox(height: 12), map]),
      ),
    );
  }
}

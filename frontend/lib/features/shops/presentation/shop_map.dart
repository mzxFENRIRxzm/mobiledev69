import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../domain/shop.dart';

class ShopMap extends StatelessWidget {
  final List<Shop> shops;
  const ShopMap({super.key, required this.shops});

  @override
  Widget build(BuildContext context) {
    final located = shops
        .where((s) => s.latitude != null && s.longitude != null)
        .toList();
    if (located.isEmpty) return const Text('ยังไม่มีร้านที่ปักหมุดบนแผนที่');
    final points = located
        .map((s) => LatLng(s.latitude!, s.longitude!))
        .toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'ร้านซ่อมบนแผนที่',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 330,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: FlutterMap(
              options: MapOptions(
                initialCenter: points.first,
                initialZoom: 13,
                initialCameraFit: points.length == 1
                    ? null
                    : CameraFit.bounds(
                        bounds: LatLngBounds.fromPoints(points),
                        padding: const EdgeInsets.all(45),
                        maxZoom: 15,
                      ),
              ),
              children: [
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'com.the_x.mobiledev69',
                ),
                MarkerLayer(
                  markers: [
                    for (final shop in located)
                      Marker(
                        point: LatLng(shop.latitude!, shop.longitude!),
                        width: 48,
                        height: 48,
                        child: IconButton.filled(
                          tooltip: shop.name,
                          icon: const Icon(Icons.build),
                          onPressed: () => showModalBottomSheet<void>(
                            context: context,
                            builder: (sheet) => Padding(
                              padding: const EdgeInsets.all(20),
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    shop.name,
                                    style: Theme.of(sheet).textTheme.titleLarge,
                                  ),
                                  Text(shop.address),
                                  const SizedBox(height: 12),
                                  Wrap(
                                    spacing: 8,
                                    children: [
                                      FilledButton(
                                        onPressed: shop.acceptingBookings
                                            ? () {
                                                Navigator.pop(sheet);
                                                context.go(
                                                  '/bookings?shop=${shop.id}',
                                                );
                                              }
                                            : null,
                                        child: const Text('จองซ่อม'),
                                      ),
                                      OutlinedButton(
                                        onPressed: () {
                                          Navigator.pop(sheet);
                                          context.go(
                                            '/messages?shop=${shop.id}',
                                          );
                                        },
                                        child: const Text('แชตร้าน'),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
                RichAttributionWidget(
                  attributions: [
                    TextSourceAttribution(
                      '© OpenStreetMap contributors',
                      onTap: () => launchUrl(
                        Uri.parse('https://www.openstreetmap.org/copyright'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'notification_store.dart';
import '../bookings/presentation/booking_view_model.dart';
import '../../core/ui/app_theme.dart';

class NotificationBell extends StatefulWidget {
  const NotificationBell({super.key});
  @override
  State<NotificationBell> createState() => _NotificationBellState();
}

class _NotificationBellState extends State<NotificationBell> {
  NotificationStore? store;
  int seen = 0;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final next = context.read<NotificationStore?>();
    if (store == next) return;
    store?.removeListener(_changed);
    store = next;
    seen = next?.announcement ?? 0;
    store?.addListener(_changed);
  }

  void _changed() {
    if (!mounted) return;
    if (store!.announcement > seen) {
      seen = store!.announcement;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('มีการแจ้งเตือนใหม่'),
          action: SnackBarAction(label: 'เปิดดู', onPressed: _open),
        ),
      );
    }
    setState(() {});
  }

  @override
  void dispose() {
    store?.removeListener(_changed);
    super.dispose();
  }

  void _open() {
    final inbox = store;
    if (inbox == null) return;
    inbox.refresh();
    final router = GoRouter.maybeOf(context);
    final bookings = context.read<BookingViewModel?>();
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColors.surface,
      isScrollControlled: true,
      showDragHandle: true,
      constraints: const BoxConstraints(maxWidth: 600),
      builder: (sheetContext) => AnimatedBuilder(
        animation: inbox,
        builder: (_, _) => SizedBox(
          height: MediaQuery.sizeOf(sheetContext).height * .72,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Row(
                  children: [
                    const Expanded(
                      child: Text(
                        'การแจ้งเตือน',
                        style: TextStyle(
                          fontSize: 21,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    TextButton(
                      onPressed: inbox.unread == 0
                          ? null
                          : () async {
                              try {
                                await inbox.markAllRead();
                              } catch (_) {
                                if (sheetContext.mounted) {
                                  ScaffoldMessenger.of(
                                    sheetContext,
                                  ).showSnackBar(
                                    const SnackBar(
                                      content: Text(
                                        'บันทึกไม่สำเร็จ กรุณาลองใหม่',
                                      ),
                                    ),
                                  );
                                }
                              }
                            },
                      child: const Text('อ่านทั้งหมด'),
                    ),
                  ],
                ),
              ),
              if (inbox.error != null)
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(inbox.error!),
                ),
              Expanded(
                child: inbox.items.isEmpty
                    ? const Center(child: Text('ยังไม่มีการแจ้งเตือน'))
                    : ListView.separated(
                        itemCount: inbox.items.length,
                        separatorBuilder: (_, _) => const Divider(height: 1),
                        itemBuilder: (_, index) {
                          final item = inbox.items[index];
                          final unread = item['read_at'] == null;
                          final room = item['conversation'];
                          final time = DateTime.tryParse(
                            item['created_at'] as String? ?? '',
                          )?.toLocal();
                          return ListTile(
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 20,
                              vertical: 8,
                            ),
                            leading: Badge(
                              isLabelVisible: unread,
                              child: Icon(
                                room != null
                                    ? Icons.chat_bubble_outline
                                    : Icons.event_note_outlined,
                              ),
                            ),
                            title: Text(
                              item['title'] as String,
                              style: TextStyle(
                                fontWeight: unread
                                    ? FontWeight.w700
                                    : FontWeight.normal,
                              ),
                            ),
                            subtitle: time == null
                                ? null
                                : Text(
                                    '${time.day}/${time.month} · ${TimeOfDay.fromDateTime(time).format(sheetContext)}',
                                  ),
                            trailing: const Icon(Icons.chevron_right, size: 18),
                            onTap: () async {
                              try {
                                await inbox.markRead(item['id'] as int);
                              } catch (_) {
                                if (!sheetContext.mounted) return;
                                ScaffoldMessenger.of(sheetContext).showSnackBar(
                                  const SnackBar(
                                    content: Text('ยังบันทึกว่าอ่านแล้วไม่ได้'),
                                  ),
                                );
                              }
                              if (!sheetContext.mounted) return;
                              Navigator.pop(sheetContext);
                              // Navigating to the current route retains its provider.
                              // Fetch the changed booking before showing that page again.
                              if (room == null) bookings?.load();
                              router?.go(
                                room != null
                                    ? '/messages?conversation=$room'
                                    : '/bookings',
                              );
                            },
                          );
                        },
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (store == null) return const SizedBox.shrink();
    return IconButton(
      onPressed: _open,
      tooltip: 'การแจ้งเตือน (${store!.unread} ยังไม่อ่าน)',
      icon: Badge(
        isLabelVisible: store!.unread > 0,
        label: Text(store!.unread > 99 ? '99+' : '${store!.unread}'),
        child: Icon(
          store!.error == null
              ? Icons.notifications_none_rounded
              : Icons.notifications_off_outlined,
        ),
      ),
    );
  }
}

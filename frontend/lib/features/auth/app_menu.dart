import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'auth_view_model.dart';
import '../../core/ui/app_theme.dart';
import '../../core/ui/app_widgets.dart';
import '../notifications/notification_bell.dart';

class TheXAppBar extends StatelessWidget implements PreferredSizeWidget {
  final String title;
  final List<Widget> actions;
  const TheXAppBar({super.key, required this.title, this.actions = const []});
  @override
  Size get preferredSize => const Size.fromHeight(76);
  @override
  Widget build(BuildContext context) => AppBar(
    automaticallyImplyLeading: false,
    title: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const BrandMark(),
        Text(
          title,
          style: const TextStyle(fontSize: 11, color: AppColors.muted),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ],
    ),
    actions: [
      ...actions,
      const NotificationBell(),
      const AppMenu(),
      const SizedBox(width: 12),
    ],
  );
}

class AppMenu extends StatelessWidget {
  const AppMenu({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthViewModel>();
    final links = <(String, String, IconData)>[
      if (!auth.isAdmin) ...[
        (
          auth.isMechanic ? '/jobs' : '/garage',
          auth.isMechanic ? 'งานซ่อม' : 'โรงรถ',
          Icons.space_dashboard_outlined,
        ),
        ('/shops', 'ร้านบริการ', Icons.storefront_outlined),
        if (!auth.isMechanic)
          ('/bookings', 'การจอง', Icons.event_note_outlined),
        if (!auth.isMechanic)
          ('/ai-chat', 'แชต AI', Icons.auto_awesome_outlined),
        ('/messages', 'ข้อความ', Icons.chat_bubble_outline),
        ('/profile', 'โปรไฟล์', Icons.person_outline),
      ],
    ];
    void select(String value) {
      if (value == 'logout') {
        auth.logout();
      } else {
        context.go(value);
      }
    }

    final route = GoRouter.maybeOf(
      context,
    )?.routeInformationProvider.value.uri.path;
    if (MediaQuery.sizeOf(context).width >= 1280 &&
        MediaQuery.textScalerOf(context).scale(14) <= 18) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (final link in links)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 2),
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: route == link.$1
                      ? AppColors.gold.withValues(alpha: .1)
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: TextButton.icon(
                  onPressed: () => select(link.$1),
                  style: TextButton.styleFrom(
                    foregroundColor: route == link.$1
                        ? AppColors.gold
                        : AppColors.muted,
                  ),
                  icon: Icon(link.$3, size: 18),
                  label: Text(link.$2),
                ),
              ),
            ),
          const SizedBox(width: 10),
          IconButton(
            onPressed: auth.loading ? null : auth.logout,
            tooltip: 'ออกจากระบบ',
            icon: const Icon(Icons.logout, size: 20),
          ),
        ],
      );
    }
    return PopupMenuButton<String>(
      tooltip: 'เมนู THE_X',
      icon: const Icon(Icons.menu),
      onSelected: select,
      itemBuilder: (_) => [
        for (final link in links)
          PopupMenuItem(
            value: link.$1,
            child: Row(
              children: [
                Icon(
                  link.$3,
                  size: 20,
                  color: route == link.$1 ? AppColors.gold : AppColors.muted,
                ),
                const SizedBox(width: 12),
                Text(link.$2),
              ],
            ),
          ),
        const PopupMenuDivider(),
        const PopupMenuItem(value: 'logout', child: Text('ออกจากระบบ')),
      ],
    );
  }
}

import 'dart:async';
export 'ai_chat_screen.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../../core/api/api_service.dart';
import '../../core/ui/app_theme.dart';
import '../../core/ui/app_widgets.dart';
import '../auth/auth_view_model.dart';
import '../auth/app_menu.dart';
import '../notifications/notification_store.dart';
import 'message_composer.dart';
import 'request_id.dart';

class MessagesScreen extends StatefulWidget {
  final int? initialShop, initialConversation;
  const MessagesScreen({super.key, this.initialShop, this.initialConversation});
  @override
  State<MessagesScreen> createState() => _MessagesScreenState();
}

class _MessagesScreenState extends State<MessagesScreen>
    with WidgetsBindingObserver {
  List<Map<String, dynamic>> conversations = [], messages = [];
  final drafts = <int, String>{};
  final retries = <int, ({String body, String id})>{};
  bool hasOlder = false, loadingOlder = false;
  int? selected;
  int generation = 0, initialization = 0;
  Timer? poller;
  bool busy = false, loading = true, loadingRooms = false, foreground = true;
  String? error;
  final input = TextEditingController();
  final scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) => _initialize());
    poller = Timer.periodic(const Duration(seconds: 5), (_) {
      if (foreground && !busy && !loadingOlder) _refresh();
    });
  }

  @override
  void didUpdateWidget(MessagesScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialConversation != widget.initialConversation ||
        oldWidget.initialShop != widget.initialShop) {
      _initialize();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    if (foreground) _refresh();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    poller?.cancel();
    input.dispose();
    scroll.dispose();
    super.dispose();
  }

  Future<void> _initialize() async {
    if (!mounted) return;
    final ticket = ++initialization;
    final api = context.read<ApiService>();
    var room = widget.initialConversation;
    try {
      if (widget.initialShop != null &&
          !context.read<AuthViewModel>().isMechanic) {
        final created = await api.request(
          'conversations/',
          method: 'POST',
          data: {'shop': widget.initialShop},
        );
        room = created['id'] as int;
      }
      if (!mounted || ticket != initialization) return;
      await _refresh(loadThread: false);
      if (!mounted || ticket != initialization) return;
      if (room != null && conversations.any((r) => r['id'] == room)) {
        await _select(room);
      } else {
        setState(() => loading = false);
      }
    } catch (e) {
      if (mounted && ticket == initialization) {
        setState(() {
          error = describeError(e);
          loading = false;
        });
      }
    }
  }

  Future<void> _refresh({bool loadThread = true}) async {
    if (!mounted || loadingRooms) return;
    loadingRooms = true;
    try {
      final list =
          (await context.read<ApiService>().request('conversations/') as List)
              .cast<Map<String, dynamic>>();
      if (!mounted) return;
      setState(() {
        conversations = list;
      });
      if (selected != null && !list.any((r) => r['id'] == selected)) {
        generation++;
        setState(() {
          selected = null;
          messages = [];
          loading = false;
          input.clear();
        });
      }
      if (loadThread && selected != null) await _loadMessages();
    } catch (e) {
      if (mounted) {
        setState(() {
          error = describeError(e);
          loading = false;
        });
      }
    } finally {
      loadingRooms = false;
    }
  }

  Future<void> _select(int id) async {
    if (busy) return;
    if (selected != null) drafts[selected!] = input.text;
    setState(() {
      selected = id;
      messages = [];
      hasOlder = false;
      loadingOlder = false;
      generation++;
      loading = true;
      error = null;
    });
    input.text = drafts[id] ?? '';
    await _loadMessages(forceScroll: true);
  }

  Future<void> _loadMessages({bool forceScroll = false}) async {
    if (!mounted || selected == null) return;
    final id = selected!;
    final ticket = ++generation;
    final api = context.read<ApiService>();
    final inbox = context.read<NotificationStore?>();
    final follow =
        forceScroll || !scroll.hasClients || scroll.position.extentAfter < 100;
    try {
      final after = messages.isEmpty ? '' : '&after=${messages.last['id']}';
      final page = await api.request(
        'conversations/$id/messages/?paged=1$after',
      );
      final items = (page is List ? page : page['results'] as List)
          .cast<Map<String, dynamic>>();
      if (!mounted || ticket != generation || selected != id) return;
      final changed =
          messages.isEmpty ||
          (items.isNotEmpty && messages.last['id'] != items.last['id']);
      setState(() {
        if (messages.isEmpty) {
          hasOlder = page is Map && page['has_more'] == true;
        }
        final merged = {
          for (final m in messages) m['id']: m,
          for (final m in items) m['id']: m,
        };
        messages = merged.values.toList()
          ..sort((a, b) => (a['id'] as int).compareTo(b['id'] as int));
        loading = false;
        error = null;
      });
      if (follow && changed) _scrollToEnd();
      // Acknowledge only messages actually fetched, never a later arrival.
      if (foreground && items.isNotEmpty) {
        await api.request(
          'conversations/$id/read/',
          method: 'POST',
          data: {'through_message': items.last['id']},
        );
        if (!mounted || ticket != generation) return;
        for (final room in conversations) {
          if (room['id'] == id) room['unread_count'] = 0;
        }
        setState(() {});
        inbox?.refresh();
      }
    } catch (e) {
      if (mounted && ticket == generation) {
        setState(() {
          error = describeError(e);
          loading = false;
        });
      }
    }
  }

  Future<void> _older() async {
    if (loadingOlder || loading || selected == null || messages.isEmpty) return;
    final room = selected, ticket = generation;
    final offset = scroll.hasClients ? scroll.offset : 0.0;
    final extent = scroll.hasClients ? scroll.position.maxScrollExtent : 0.0;
    setState(() => loadingOlder = true);
    try {
      final page = await context.read<ApiService>().request(
        'conversations/$room/messages/?paged=1&before=${messages.first['id']}',
      );
      if (!mounted || room != selected || ticket != generation) return;
      final items = (page['results'] as List).cast<Map<String, dynamic>>();
      setState(() {
        final merged = {
          for (final m in messages) m['id']: m,
          for (final m in items) m['id']: m,
        };
        messages = merged.values.toList()
          ..sort((a, b) => (a['id'] as int).compareTo(b['id'] as int));
        hasOlder = page['has_more'] == true;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && room == selected && scroll.hasClients) {
          scroll.jumpTo(
            (offset + scroll.position.maxScrollExtent - extent).clamp(
              0.0,
              scroll.position.maxScrollExtent,
            ),
          );
        }
      });
    } catch (e) {
      if (mounted && room == selected) setState(() => error = describeError(e));
    } finally {
      if (mounted && room == selected) setState(() => loadingOlder = false);
    }
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !scroll.hasClients) return;
      if (MediaQuery.disableAnimationsOf(context)) {
        scroll.jumpTo(scroll.position.maxScrollExtent);
      } else {
        scroll.animateTo(
          scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 180),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send() async {
    final body = input.text.trim();
    final room = selected;
    if (body.isEmpty || room == null || busy || loading) return;
    setState(() {
      busy = true;
      error = null;
      if (retries[room]?.body != body) {
        retries[room] = (body: body, id: newMessageRequestId());
      }
    });
    try {
      await context.read<ApiService>().request(
        'conversations/$room/messages/',
        method: 'POST',
        data: {'body': body, 'request_id': retries[room]!.id},
      );
      if (!mounted) return;
      input.clear();
      drafts.remove(room);
      retries.remove(room);
      await _loadMessages(forceScroll: true);
      await _refresh(loadThread: false);
    } catch (e) {
      if (mounted) setState(() => error = describeError(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  String _time(dynamic value) {
    final date = DateTime.tryParse(value as String? ?? '')?.toLocal();
    if (date == null) return '';
    return '${date.day}/${date.month} · ${TimeOfDay.fromDateTime(date).format(context)}';
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthViewModel>();
    final room = conversations.where((r) => r['id'] == selected).firstOrNull;
    final title = room == null
        ? 'บทสนทนา'
        : (auth.isMechanic ? room['customer_name'] : room['shop_name'])
              as String;
    return Scaffold(
      appBar: const TheXAppBar(title: 'ข้อความ'),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1240),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Card(
              margin: EdgeInsets.zero,
              child: LayoutBuilder(
                builder: (context, size) {
                  final compact =
                      size.maxWidth < 760 ||
                      MediaQuery.textScalerOf(context).scale(14) > 20;
                  final roomList = Column(
                    children: [
                      Padding(
                        padding: const EdgeInsets.all(20),
                        child: Row(
                          children: [
                            const Expanded(
                              child: Text(
                                'กล่องข้อความ',
                                style: TextStyle(
                                  fontSize: 22,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            IconButton(
                              onPressed: () => _refresh(),
                              tooltip: 'โหลดข้อความใหม่',
                              icon: const Icon(Icons.refresh),
                            ),
                          ],
                        ),
                      ),
                      const Divider(height: 1),
                      Expanded(
                        child: conversations.isEmpty
                            ? ListView(
                                children: [
                                  const EmptyPanel(
                                    icon: Icons.forum_outlined,
                                    title: 'ยังไม่มีบทสนทนา',
                                    subtitle:
                                        'เลือกหน้าร้านเพื่อเริ่มสอบถามบริการ',
                                  ),
                                  if (!auth.isMechanic)
                                    Center(
                                      child: TextButton(
                                        onPressed: () => context.go('/shops'),
                                        child: const Text('ค้นหาร้านบริการ'),
                                      ),
                                    ),
                                ],
                              )
                            : ListView.builder(
                                itemCount: conversations.length,
                                itemBuilder: (_, index) {
                                  final r = conversations[index];
                                  final name =
                                      (auth.isMechanic
                                              ? r['customer_name']
                                              : r['shop_name'])
                                          as String;
                                  final unread = r['unread_count'] as int? ?? 0;
                                  return Padding(
                                    padding: const EdgeInsets.fromLTRB(
                                      8,
                                      6,
                                      8,
                                      0,
                                    ),
                                    child: ListTile(
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(14),
                                      ),
                                      selected: r['id'] == selected,
                                      selectedColor: AppColors.gold,
                                      selectedTileColor: AppColors.gold
                                          .withValues(alpha: .09),
                                      leading: CircleAvatar(
                                        backgroundColor: AppColors.gold
                                            .withValues(alpha: .12),
                                        child: Icon(
                                          auth.isMechanic
                                              ? Icons.person_outline
                                              : Icons.storefront_outlined,
                                          color: AppColors.gold,
                                        ),
                                      ),
                                      title: Text(
                                        name,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: TextStyle(
                                          fontWeight: unread > 0
                                              ? FontWeight.bold
                                              : FontWeight.w500,
                                        ),
                                      ),
                                      subtitle: Text(
                                        r['last_message'] as String? ??
                                            'เริ่มบทสนทนา',
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                      trailing: unread > 0
                                          ? Badge(label: Text('$unread'))
                                          : null,
                                      onTap: busy
                                          ? null
                                          : () => _select(r['id'] as int),
                                    ),
                                  );
                                },
                              ),
                      ),
                    ],
                  );
                  final thread = Column(
                    children: [
                      Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 12,
                        ),
                        child: Row(
                          children: [
                            if (compact)
                              IconButton(
                                tooltip: 'กลับกล่องข้อความ',
                                onPressed: busy
                                    ? null
                                    : () {
                                        if (selected != null) {
                                          drafts[selected!] = input.text;
                                        }
                                        generation++;
                                        setState(() {
                                          selected = null;
                                          messages = [];
                                          loading = false;
                                        });
                                      },
                                icon: const Icon(Icons.arrow_back),
                              ),
                            const Icon(
                              Icons.chat_bubble_outline,
                              color: AppColors.gold,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    title,
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w700,
                                      fontSize: 18,
                                    ),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  Text(
                                    'คุยกับ${auth.isMechanic ? 'ลูกค้า' : 'ร้านบริการ'} · อัปเดตทุก 5 วินาที',
                                    style: Theme.of(
                                      context,
                                    ).textTheme.bodySmall,
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                      const Divider(height: 1),
                      if (loading) const LinearProgressIndicator(),
                      Expanded(
                        child: selected == null
                            ? const Center(
                                child: EmptyPanel(
                                  icon: Icons.forum_outlined,
                                  title: 'ทุกเรื่องรถ คุยกันได้ที่นี่',
                                  subtitle:
                                      'เลือกบทสนทนาจากกล่องข้อความเพื่อเริ่มคุย',
                                ),
                              )
                            : ListView(
                                controller: scroll,
                                padding: const EdgeInsets.all(20),
                                children: [
                                  if (hasOlder)
                                    TextButton(
                                      onPressed: loadingOlder ? null : _older,
                                      child: Text(
                                        loadingOlder
                                            ? 'กำลังโหลด…'
                                            : 'โหลดข้อความก่อนหน้า',
                                      ),
                                    ),
                                  if (!loading && messages.isEmpty)
                                    const EmptyPanel(
                                      icon: Icons.waving_hand_outlined,
                                      title: 'เริ่มต้นด้วยคำทักทาย',
                                      subtitle:
                                          'สอบถามบริการหรือนัดหมายกับร้านได้เลย',
                                    ),
                                  for (final message in messages)
                                    Align(
                                      alignment:
                                          message['sender_name'] ==
                                              auth.username
                                          ? Alignment.centerRight
                                          : Alignment.centerLeft,
                                      child: ConstrainedBox(
                                        constraints: BoxConstraints(
                                          maxWidth: compact
                                              ? size.maxWidth * .82
                                              : 520,
                                        ),
                                        child: Container(
                                          margin: const EdgeInsets.only(
                                            bottom: 14,
                                          ),
                                          padding: const EdgeInsets.symmetric(
                                            horizontal: 16,
                                            vertical: 12,
                                          ),
                                          decoration: BoxDecoration(
                                            color:
                                                message['sender_name'] ==
                                                    auth.username
                                                ? Theme.of(
                                                    context,
                                                  ).colorScheme.primaryContainer
                                                : const Color(0xff252830),
                                            borderRadius: BorderRadius.circular(
                                              18,
                                            ),
                                          ),
                                          child: Column(
                                            crossAxisAlignment:
                                                CrossAxisAlignment.start,
                                            children: [
                                              if (message['sender_name'] !=
                                                  auth.username)
                                                Text(
                                                  message['sender_name']
                                                      as String,
                                                  style: const TextStyle(
                                                    fontSize: 12,
                                                    color: AppColors.gold,
                                                  ),
                                                ),
                                              SelectableText(
                                                message['body'] as String,
                                              ),
                                              const SizedBox(height: 5),
                                              Text(
                                                _time(message['created_at']),
                                                style: const TextStyle(
                                                  fontSize: 11,
                                                  color: AppColors.muted,
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ),
                                    ),
                                ],
                              ),
                      ),
                      if (selected != null) ...[
                        const Divider(height: 1),
                        MessageComposer(
                          controller: input,
                          onSend: _send,
                          enabled: !busy && !loading,
                          hint: auth.isMechanic
                              ? 'พิมพ์ข้อความถึงลูกค้า…'
                              : 'พิมพ์ข้อความถึงร้าน…',
                        ),
                      ],
                    ],
                  );
                  return Column(
                    children: [
                      if (error != null)
                        MaterialBanner(
                          content: Text(error!),
                          actions: [
                            TextButton(
                              onPressed: () => _refresh(),
                              child: const Text('ลองใหม่'),
                            ),
                          ],
                        ),
                      Expanded(
                        child: compact
                            ? (selected == null ? roomList : thread)
                            : Row(
                                children: [
                                  SizedBox(width: 320, child: roomList),
                                  const VerticalDivider(width: 1),
                                  Expanded(child: thread),
                                ],
                              ),
                      ),
                    ],
                  );
                },
              ),
            ),
          ),
        ),
      ),
    );
  }
}

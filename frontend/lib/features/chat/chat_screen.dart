import 'dart:async';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../../core/api/api_service.dart';
import '../auth/auth_view_model.dart';
import '../auth/app_menu.dart';

class MessagesScreen extends StatefulWidget {
  final int? initialShop;
  const MessagesScreen({super.key, this.initialShop});
  @override
  State<MessagesScreen> createState() => _MessagesScreenState();
}

class _MessagesScreenState extends State<MessagesScreen> {
  List<Map<String, dynamic>> conversations = [], messages = [];
  int? selected;
  Timer? poller;
  bool busy = false;
  String? error;
  final input = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load(initial: true));
    poller = Timer.periodic(const Duration(seconds: 8), (_) => _load());
  }

  @override
  void dispose() {
    poller?.cancel();
    input.dispose();
    super.dispose();
  }

  Future<void> _load({bool initial = false}) async {
    if (busy || !mounted) return;
    try {
      final api = context.read<ApiService>();
      final isMechanic = context.read<AuthViewModel>().isMechanic;
      var list = (await api.request('conversations/') as List)
          .cast<Map<String, dynamic>>();
      if (initial && widget.initialShop != null && !isMechanic) {
        final room = await api.request(
          'conversations/',
          method: 'POST',
          data: {'shop': widget.initialShop},
        );
        selected = room['id'] as int;
        list = (await api.request('conversations/') as List)
            .cast<Map<String, dynamic>>();
      }
      selected ??= list.isEmpty ? null : list.first['id'] as int;
      final items = selected == null
          ? <Map<String, dynamic>>[]
          : (await api.request('conversations/$selected/messages/') as List)
                .cast<Map<String, dynamic>>();
      if (mounted) {
        setState(() {
          conversations = list;
          messages = items;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = describeError(e));
    }
  }

  Future<void> _send() async {
    final body = input.text.trim();
    if (body.isEmpty || selected == null || busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await context.read<ApiService>().request(
        'conversations/$selected/messages/',
        method: 'POST',
        data: {'body': body},
      );
      input.clear();
    } catch (e) {
      if (mounted) setState(() => error = describeError(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthViewModel>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('แชตข้อความ'),
        actions: [
          IconButton(
            onPressed: () => _load(),
            tooltip: 'โหลดข้อความใหม่',
            icon: const Icon(Icons.refresh),
          ),
          TextButton(
            onPressed: () => context.go(auth.isMechanic ? '/jobs' : '/garage'),
            child: const Text('หน้าหลัก'),
          ),
          const AppMenu(),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1100),
          child: Column(
            children: [
              if (error != null)
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(
                    error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              Expanded(
                child: LayoutBuilder(
                  builder: (context, size) {
                    final roomList = ListView(
                      children: [
                        for (final room in conversations)
                          ListTile(
                            selected: room['id'] == selected,
                            title: Text(
                              auth.isMechanic
                                  ? room['customer_name'] as String
                                  : room['shop_name'] as String,
                            ),
                            subtitle: auth.isMechanic
                                ? Text(room['shop_name'] as String)
                                : null,
                            onTap: () {
                              setState(() {
                                selected = room['id'] as int;
                                messages = [];
                              });
                              _load();
                            },
                          ),
                        if (conversations.isEmpty)
                          Padding(
                            padding: const EdgeInsets.all(20),
                            child: Column(
                              children: [
                                const Text('ยังไม่มีห้องสนทนา'),
                                if (!auth.isMechanic)
                                  TextButton(
                                    onPressed: () => context.go('/shops'),
                                    child: const Text('เลือกร้านเพื่อเริ่มแชต'),
                                  ),
                              ],
                            ),
                          ),
                      ],
                    );
                    final thread = Column(
                      children: [
                        Expanded(
                          child: ListView(
                            padding: const EdgeInsets.all(16),
                            children: [
                              for (final message in messages)
                                Align(
                                  alignment:
                                      message['sender_name'] == auth.username
                                      ? Alignment.centerRight
                                      : Alignment.centerLeft,
                                  child: Card(
                                    child: Padding(
                                      padding: const EdgeInsets.all(12),
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            message['sender_name'] as String,
                                            style: const TextStyle(
                                              fontWeight: FontWeight.bold,
                                            ),
                                          ),
                                          Text(message['body'] as String),
                                        ],
                                      ),
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                        if (selected != null)
                          Padding(
                            padding: const EdgeInsets.all(12),
                            child: Row(
                              children: [
                                Expanded(
                                  child: TextField(
                                    controller: input,
                                    maxLength: 2000,
                                    minLines: 1,
                                    maxLines: 3,
                                    decoration: const InputDecoration(
                                      hintText: 'พิมพ์ข้อความถึงร้าน',
                                    ),
                                    onSubmitted: (_) => _send(),
                                  ),
                                ),
                                IconButton(
                                  onPressed: busy ? null : _send,
                                  tooltip: 'ส่งข้อความ',
                                  icon: const Icon(Icons.send),
                                ),
                              ],
                            ),
                          ),
                      ],
                    );
                    return size.maxWidth < 650
                        ? Column(
                            children: [
                              SizedBox(height: 140, child: roomList),
                              Expanded(child: thread),
                            ],
                          )
                        : Row(
                            children: [
                              SizedBox(width: 270, child: roomList),
                              const VerticalDivider(width: 1),
                              Expanded(child: thread),
                            ],
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
}

class AiChatScreen extends StatefulWidget {
  const AiChatScreen({super.key});
  @override
  State<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends State<AiChatScreen> {
  final input = TextEditingController();
  final messages = <(bool, String)>[];
  bool busy = false;
  String? error;
  @override
  void dispose() {
    input.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final prompt = input.text.trim();
    if (prompt.isEmpty || busy) return;
    setState(() {
      busy = true;
      error = null;
      messages.add((true, prompt));
      input.clear();
    });
    try {
      final result = await context.read<ApiService>().request(
        'ai-chat/',
        method: 'POST',
        data: {'message': prompt},
      );
      if (mounted) {
        setState(() => messages.add((false, result['reply'] as String)));
      }
    } catch (e) {
      if (mounted) setState(() => error = describeError(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('แชต AI'),
      actions: [
        TextButton(
          onPressed: () => context.go('/garage'),
          child: const Text('หน้าหลัก'),
        ),
        const AppMenu(),
      ],
    ),
    body: Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 800),
        child: Column(
          children: [
            const Padding(
              padding: EdgeInsets.all(12),
              child: Text(
                'ผู้ช่วยข้อมูลทั่วไปเกี่ยวกับรถจักรยานยนต์ คำตอบอาจผิดพลาดได้ และไม่ใช่การวินิจฉัยจากช่าง',
              ),
            ),
            if (error != null)
              Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  for (final item in messages)
                    Align(
                      alignment: item.$1
                          ? Alignment.centerRight
                          : Alignment.centerLeft,
                      child: Card(
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Text(item.$2),
                        ),
                      ),
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: input,
                      maxLength: 1000,
                      minLines: 1,
                      maxLines: 3,
                      decoration: const InputDecoration(
                        hintText: 'ถามผู้ช่วย AI',
                      ),
                    ),
                  ),
                  IconButton(
                    onPressed: busy ? null : _send,
                    icon: const Icon(Icons.send),
                    tooltip: 'ส่งคำถาม',
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

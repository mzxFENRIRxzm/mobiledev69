import 'dart:async';
import 'request_id.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/api/api_service.dart';
import '../auth/app_menu.dart';
import '../../core/ui/app_widgets.dart';
import '../../core/ui/app_theme.dart';
import 'message_composer.dart';

class AiChatScreen extends StatefulWidget {
  const AiChatScreen({super.key});
  @override
  State<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends State<AiChatScreen> {
  final input = TextEditingController();
  final scroll = ScrollController();
  List<Map<String, dynamic>> rooms = [], turns = [];
  String? selected, error, retryId, retryText;
  bool busy = false, loading = true, hasOlder = false, loadingOlder = false;
  int generation = 0;
  Timer? poller;
  bool get pending => turns.any((t) => t['status'] == 'pending');

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _initialize());
    poller = Timer.periodic(const Duration(seconds: 5), (_) {
      if (mounted && pending && !busy && !loading && !loadingOlder) {
        _select(selected!);
      }
    });
  }

  @override
  void dispose() {
    poller?.cancel();
    input.dispose();
    scroll.dispose();
    super.dispose();
  }

  Future<void> _initialize() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = await context.read<ApiService>().request(
        'ai-conversations/',
      );
      if (!mounted) return;
      setState(() => rooms = (result as List).cast<Map<String, dynamic>>());
      if (rooms.isNotEmpty) {
        await _select(rooms.first['id'] as String);
      } else {
        setState(() => loading = false);
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          loading = false;
          error = describeError(e);
        });
      }
    }
  }

  Future<void> _select(String id) async {
    final ticket = ++generation;
    final sameRoom = selected == id;
    setState(() {
      loading = true;
      selected = id;
      if (!sameRoom) {
        turns = [];
        hasOlder = false;
        loadingOlder = false;
      }
    });
    try {
      final result = await context.read<ApiService>().request(
        'ai-conversations/$id/?paged=1',
      );
      if (!mounted || ticket != generation) return;
      setState(() {
        final items = (result['turns'] as List).cast<Map<String, dynamic>>();
        if (turns.isEmpty) hasOlder = result['has_more'] == true;
        final merged = {
          for (final t in turns) t['id']: t,
          for (final t in items) t['id']: t,
        };
        turns = merged.values.toList()
          ..sort((a, b) => (a['id'] as int).compareTo(b['id'] as int));
        loading = false;
      });
      _scrollToEnd();
    } catch (e) {
      if (mounted && ticket == generation) {
        setState(() {
          loading = false;
          error = describeError(e);
        });
      }
    }
  }

  Future<void> _older() async {
    if (loadingOlder || loading || selected == null || turns.isEmpty) return;
    final room = selected, ticket = generation;
    final offset = scroll.hasClients ? scroll.offset : 0.0;
    final extent = scroll.hasClients ? scroll.position.maxScrollExtent : 0.0;
    setState(() => loadingOlder = true);
    try {
      final page = await context.read<ApiService>().request(
        'ai-conversations/$room/?paged=1&before=${turns.first['id']}',
      );
      if (!mounted || selected != room || generation != ticket) return;
      setState(() {
        final items = (page['turns'] as List).cast<Map<String, dynamic>>();
        final merged = {
          for (final t in turns) t['id']: t,
          for (final t in items) t['id']: t,
        };
        turns = merged.values.toList()
          ..sort((a, b) => (a['id'] as int).compareTo(b['id'] as int));
        hasOlder = page['has_more'] == true;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && selected == room && scroll.hasClients) {
          scroll.jumpTo(
            (offset + scroll.position.maxScrollExtent - extent).clamp(
              0.0,
              scroll.position.maxScrollExtent,
            ),
          );
        }
      });
    } catch (e) {
      if (mounted && selected == room) setState(() => error = describeError(e));
    } finally {
      if (mounted && selected == room) setState(() => loadingOlder = false);
    }
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && scroll.hasClients) {
        scroll.animateTo(
          scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send({Map<String, dynamic>? retry}) async {
    final prompt = retry?['message'] as String? ?? input.text.trim();
    if (prompt.isEmpty || busy || loading || pending) return;
    final id =
        retry?['request_id'] as String? ??
        (retryText == prompt ? retryId : null) ??
        newMessageRequestId();
    setState(() {
      busy = true;
      error = null;
      retryText = prompt;
      retryId = id;
    });
    final api = context.read<ApiService>();
    try {
      if (selected == null) {
        final room = await api.request(
          'ai-conversations/',
          method: 'POST',
          data: {},
        );
        if (!mounted) return;
        setState(() {
          selected = room['id'] as String;
          rooms.insert(0, Map<String, dynamic>.from(room));
        });
      }
      await api.request(
        'ai-chat/',
        method: 'POST',
        data: {
          'message': prompt,
          'conversation_id': selected,
          'request_id': id,
        },
      );
      if (!mounted) return;
      input.clear();
      retryId = retryText = null;
    } catch (e) {
      if (mounted) setState(() => error = describeError(e));
    } finally {
      if (mounted) {
        setState(() => busy = false);
        if (selected != null) await _select(selected!);
      }
    }
  }

  void _newChat() {
    generation++;
    input.clear();
    setState(() {
      selected = null;
      turns = [];
      retryId = retryText = error = null;
      loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: TheXAppBar(
        title: 'ผู้ช่วย AI',
        actions: [
          IconButton(
            onPressed: busy || loading ? null : _newChat,
            tooltip: 'บทสนทนาใหม่',
            icon: const Icon(Icons.add_comment_outlined),
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 850),
          child: Column(
            children: [
              if (rooms.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: DropdownButton<String>(
                    isExpanded: true,
                    value: selected,
                    hint: const Text('เลือกประวัติสนทนา หรือเริ่มคำถามใหม่'),
                    items: rooms
                        .map(
                          (r) => DropdownMenuItem<String>(
                            value: r['id'] as String,
                            child: Text(
                              r['title'] as String,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: busy || loading
                        ? null
                        : (id) {
                            if (id != null) {
                              input.clear();
                              retryId = retryText = error = null;
                              _select(id);
                            }
                          },
                  ),
                ),
              if (error != null)
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          error!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ),
                      IconButton(
                        tooltip: 'โหลดประวัติใหม่',
                        onPressed: busy || loading ? null : _initialize,
                        icon: const Icon(Icons.refresh),
                      ),
                    ],
                  ),
                ),
              if (loading) const LinearProgressIndicator(),
              Expanded(
                child: ListView(
                  controller: scroll,
                  padding: const EdgeInsets.all(16),
                  children: [
                    const Card(
                      child: Padding(
                        padding: EdgeInsets.all(16),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(
                              Icons.info_outline,
                              size: 20,
                              color: AppColors.gold,
                            ),
                            SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                'ผู้ช่วยข้อมูลรถจักรยานยนต์ คำตอบอาจผิดพลาดได้ ไม่ใช่การวินิจฉัยจากช่าง\n'
                                'คำถามส่งไปยัง Google Gemini กรุณาไม่ใส่ชื่อ เบอร์โทร ที่อยู่ หรือทะเบียนรถ',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: AppColors.muted,
                                  height: 1.7,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    if (!loading && turns.isEmpty)
                      Reveal(
                        child: Column(
                          children: [
                            const EmptyPanel(
                              icon: Icons.auto_awesome_outlined,
                              title: 'วันนี้ให้ช่วยเรื่องรถอะไรดี?',
                              subtitle:
                                  'เริ่มจากรุ่นรถ ปี และอาการที่พบ เช่น สตาร์ตยากหรือมีเสียงผิดปกติ',
                            ),
                            Wrap(
                              alignment: WrapAlignment.center,
                              spacing: 10,
                              runSpacing: 10,
                              children: [
                                for (final prompt in [
                                  'ควรเช็กอะไรบ้างก่อนเดินทางไกล',
                                  'รถสตาร์ตยาก ควรเริ่มตรวจอะไร',
                                  'เตรียมข้อมูลอะไรให้ช่างก่อนจองซ่อม',
                                ])
                                  ActionChip(
                                    label: Text(prompt),
                                    onPressed: busy
                                        ? null
                                        : () {
                                            input.text = prompt;
                                            input.selection =
                                                TextSelection.collapsed(
                                                  offset: prompt.length,
                                                );
                                          },
                                  ),
                              ],
                            ),
                            const SizedBox(height: 20),
                          ],
                        ),
                      ),
                    if (hasOlder)
                      TextButton(
                        onPressed: loadingOlder ? null : _older,
                        child: const Text('โหลดข้อความก่อนหน้า'),
                      ),
                    for (final turn in turns) ...[
                      Align(
                        alignment: Alignment.centerRight,
                        child: Card(
                          color: Theme.of(context).colorScheme.primaryContainer,
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: SelectableText(turn['message'] as String),
                          ),
                        ),
                      ),
                      if (turn['status'] == 'completed')
                        Align(
                          alignment: Alignment.centerLeft,
                          child: Card(
                            child: Padding(
                              padding: const EdgeInsets.all(12),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  SelectableText(turn['reply'] as String),
                                  const SizedBox(height: 8),
                                  Text(
                                    (turn['sources'] as List).isEmpty
                                        ? 'ข้อมูลทั่วไป — ไม่มีคู่มืออ้างอิงในคำตอบนี้'
                                        : 'แหล่งข้อมูลประกอบคำตอบ',
                                  ),
                                  for (final source in turn['sources'] as List)
                                    TextButton(
                                      onPressed: () {
                                        final uri = Uri.tryParse(
                                          source['url'] as String,
                                        );
                                        if (uri != null &&
                                            [
                                              'https',
                                              'http',
                                            ].contains(uri.scheme)) {
                                          launchUrl(uri);
                                        }
                                      },
                                      child: Text(
                                        '${source['title']} ${source['locator'] ?? ''}',
                                      ),
                                    ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      if (turn['status'] == 'pending')
                        const ListTile(
                          leading: CircularProgressIndicator(),
                          title: Text('กำลังรอคำตอบ…'),
                        ),
                      if (turn['status'] == 'failed')
                        ListTile(
                          title: Text(
                            turn['error_code'] == 'rate_limited'
                                ? 'AI ใช้โควตาครบ กรุณารอแล้วลองใหม่'
                                : 'ยังไม่ได้รับคำตอบ',
                          ),
                          trailing: TextButton(
                            onPressed: busy || loading || pending
                                ? null
                                : () => _send(retry: turn),
                            child: const Text('ลองอีกครั้ง'),
                          ),
                        ),
                    ],
                  ],
                ),
              ),
              if (busy)
                const Padding(
                  padding: EdgeInsets.all(8),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                      SizedBox(width: 12),
                      Text('กำลังให้ AI ตรวจคำถาม…'),
                    ],
                  ),
                ),
              MessageComposer(
                controller: input,
                onSend: _send,
                enabled: !busy && !loading && !pending,
                maxLength: 1000,
                hint: 'ถามผู้ช่วย AI',
                sendLabel: 'ส่งคำถาม',
              ),
            ],
          ),
        ),
      ),
    );
  }
}

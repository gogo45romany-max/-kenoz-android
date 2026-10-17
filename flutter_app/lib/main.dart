import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() => runApp(const KenozApp());

const navy = Color(0xFF123044);
const gold = Color(0xFFBD9653);
const cream = Color(0xFFF8F7F2);
const apiRoot = 'https://api.coptic.io/api';

class KenozApp extends StatelessWidget {
  const KenozApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'كنوز',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(useMaterial3: true, scaffoldBackgroundColor: cream,
      colorScheme: ColorScheme.fromSeed(seedColor: navy, primary: navy, secondary: gold),
      appBarTheme: const AppBarTheme(backgroundColor: navy, foregroundColor: Colors.white, centerTitle: true),
      fontFamily: 'sans-serif'),
    home: const HomePage(),
  );
}

class LocalStore {
  static Future<Directory> _dir() async {
    final base = await getApplicationDocumentsDirectory();
    final d = Directory('${base.path}/kenoz_cache');
    if (!await d.exists()) await d.create(recursive: true);
    return d;
  }
  static String _safe(String key) => base64Url.encode(utf8.encode(key)).replaceAll('=', '');
  static Future<void> save(String key, String data) async {
    final d = await _dir();
    await File('${d.path}/${_safe(key)}.json').writeAsString(data, flush: true);
  }
  static Future<String?> read(String key) async {
    try {
      final d = await _dir();
      final f = File('${d.path}/${_safe(key)}.json');
      if (await f.exists()) return await f.readAsString();
    } catch (_) {}
    return null;
  }
}

class ApiResult {
  final dynamic data;
  final bool offline;
  const ApiResult(this.data, this.offline);
}

class KenozApi {
  static Future<ApiResult> get(String path, {Map<String, String>? query}) async {
    final uri = Uri.parse('$apiRoot$path').replace(queryParameters: query);
    final key = uri.toString();
    try {
      final response = await http.get(uri, headers: {'Accept':'application/json'}).timeout(const Duration(seconds: 12));
      if (response.statusCode < 200 || response.statusCode >= 300) throw HttpException('HTTP ${response.statusCode}');
      final body = utf8.decode(response.bodyBytes);
      final decoded = jsonDecode(body);
      await LocalStore.save(key, body);
      return ApiResult(decoded, false);
    } catch (_) {
      final saved = await LocalStore.read(key);
      if (saved != null) return ApiResult(jsonDecode(saved), true);
      rethrow;
    }
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});
  @override State<HomePage> createState() => _HomePageState();
}
class _HomePageState extends State<HomePage> {
  int tab = 0;
  final pages = const [DashboardPage(), BiblePage(), PrayerPage(), ChurchPage(), NotesPage()];
  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('كنوز ✝'), actions: [IconButton(tooltip:'حول التطبيق',onPressed:()=>showAboutDialog(context:context,applicationName:'كنوز KENOZ',applicationVersion:'1.0.0',children:const [Text('تطبيق قبطي أرثوذكسي قيد التطوير. تُحفظ البيانات التي يتم تحميلها تلقائيًا لاستخدامها دون إنترنت.')]),icon:const Icon(Icons.info_outline))]),
    body: IndexedStack(index:tab,children:pages),
    bottomNavigationBar: NavigationBar(selectedIndex:tab,onDestinationSelected:(i)=>setState(()=>tab=i),destinations:const [
      NavigationDestination(icon:Icon(Icons.home_outlined),selectedIcon:Icon(Icons.home),label:'الرئيسية'),
      NavigationDestination(icon:Icon(Icons.menu_book_outlined),selectedIcon:Icon(Icons.menu_book),label:'الكتاب'),
      NavigationDestination(icon:Icon(Icons.auto_stories_outlined),selectedIcon:Icon(Icons.auto_stories),label:'الأجبية'),
      NavigationDestination(icon:Icon(Icons.church_outlined),selectedIcon:Icon(Icons.church),label:'الكنيسة'),
      NavigationDestination(icon:Icon(Icons.edit_note),selectedIcon:Icon(Icons.edit_note),label:'ملاحظاتي'),
    ]),
  );
}

class DashboardPage extends StatelessWidget {
  const DashboardPage({super.key});
  @override Widget build(BuildContext context) => ListView(padding:const EdgeInsets.all(18),children:[
    Container(padding:const EdgeInsets.all(22),decoration:BoxDecoration(gradient:const LinearGradient(colors:[navy,Color(0xFF20536A)]),borderRadius:BorderRadius.circular(22)),child:const Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text('سلام ونعمة ✝',style:TextStyle(color:gold,fontSize:16)),SizedBox(height:8),Text('كنوز الإيمان',style:TextStyle(color:Colors.white,fontSize:27,fontWeight:FontWeight.bold)),SizedBox(height:8),Text('صلِّ، اقرأ، وتعلّم كل يوم',style:TextStyle(color:Colors.white70,fontSize:15))])),
    const SizedBox(height:18),
    const SectionCard(title:'قراءات اليوم',subtitle:'القطمارس والسنكسار والصوم والموسم الطقسي',icon:Icons.calendar_month,child:DailyReadings()),
    const SizedBox(height:12),
    const Text('مكتبة كنوز',style:TextStyle(fontSize:20,fontWeight:FontWeight.bold,color:navy)),
    const SizedBox(height:10),
    Wrap(spacing:10,runSpacing:10,children:[
      _shortcut(context,'الكتاب المقدس',Icons.menu_book,1),
      _shortcut(context,'الأجبية',Icons.auto_stories,2),
      _shortcut(context,'القطمارس والسنكسار',Icons.event_note,3),
      _shortcut(context,'ملاحظاتي',Icons.note_alt,4),
    ]),
    const SizedBox(height:16),
    const Text('المحتوى الذي يُحمّل بنجاح يُحفظ تلقائيًا على الجهاز. أول تحميل يحتاج اتصالًا بالإنترنت.',style:TextStyle(height:1.6,color:Colors.black54)),
  ]);
  Widget _shortcut(BuildContext c,String t,IconData i,int tab) {
    final today=DateTime.now().toIso8601String().substring(0,10);
    final path=tab==3?'/synaxarium/$today':'/readings/$today?detailed=true';
    return SizedBox(width:MediaQuery.of(c).size.width/2-24,child:Card(color:Colors.white,child:InkWell(
      borderRadius:BorderRadius.circular(14),
      onTap:()=>Navigator.of(c).push(MaterialPageRoute(builder:(_)=>DetailPage(title:t,path:path))),
      child:Padding(padding:const EdgeInsets.all(16),child:Column(children:[Icon(i,color:gold,size:30),const SizedBox(height:8),Text(t,textAlign:TextAlign.center,style:const TextStyle(fontWeight:FontWeight.bold))]))
    )));
  }
}

class SectionCard extends StatelessWidget {
  final String title,subtitle; final IconData icon; final Widget child;
  const SectionCard({super.key,required this.title,required this.subtitle,required this.icon,required this.child});
  @override Widget build(BuildContext context)=>Card(color:Colors.white,child:Padding(padding:const EdgeInsets.all(14),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Row(children:[Icon(icon,color:gold),const SizedBox(width:8),Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text(title,style:const TextStyle(fontWeight:FontWeight.bold,fontSize:17)),Text(subtitle,style:const TextStyle(color:Colors.black54,fontSize:12))]))]),const SizedBox(height:12),child])));
}

class DailyReadings extends StatelessWidget {
  const DailyReadings({super.key});
  @override Widget build(BuildContext context)=>Wrap(spacing:8,runSpacing:8,children:[
    _btn(context,'قراءات القطمارس',()=>Navigator.push(context,MaterialPageRoute(builder:(_)=>DetailPage(title:'قراءات القطمارس',path:'/readings/${DateTime.now().toIso8601String().substring(0,10)}?detailed=true')))),
    _btn(context,'سنكسار اليوم',()=>Navigator.push(context,MaterialPageRoute(builder:(_)=>DetailPage(title:'سنكسار اليوم',path:'/synaxarium/${DateTime.now().toIso8601String().substring(0,10)}')))),
    _btn(context,'الصوم والموسم',()=>Navigator.push(context,MaterialPageRoute(builder:(_)=>DetailPage(title:'الصوم',path:'/fasting/${DateTime.now().toIso8601String().substring(0,10)}')))),
  ]);
  Widget _btn(BuildContext c,String s,VoidCallback f)=>OutlinedButton(onPressed:f,child:Text(s));
}

class BiblePage extends StatefulWidget { const BiblePage({super.key}); @override State<BiblePage> createState()=>_BiblePageState(); }
class _BiblePageState extends State<BiblePage> {
  List<dynamic> books=[]; bool loading=true; String error=''; int bookIndex=0,chapterIndex=0; String query='';
  @override void initState(){super.initState();_load();}
  Future<void> _load() async {try{final raw=await rootBundle.loadString('assets/bible-data.json');final d=jsonDecode(raw) as Map<String,dynamic>;final b=(d['books'] as List<dynamic>? ?? []);if(!mounted)return;setState(()=>books=b);}catch(e){if(mounted)setState(()=>error='تعذر فتح ملف الكتاب المقدس: $e');}finally{if(mounted)setState(()=>loading=false);}}
  @override Widget build(BuildContext context){
    if(loading)return const Center(child:CircularProgressIndicator());
    if(books.isEmpty)return Center(child:Padding(padding:const EdgeInsets.all(24),child:Text(error.isEmpty?'سيتم تجهيز بيانات الكتاب المقدس أثناء البناء.':error,textAlign:TextAlign.center)));
    final b=books[bookIndex] as Map<String,dynamic>;
    final chapters=(b['chapters'] as List<dynamic>? ?? []);
    final chapter=chapters.isEmpty?null:chapters[chapterIndex] as Map<String,dynamic>;
    final verses=(chapter?['verses'] as List<dynamic>? ?? []);
    return ListView(padding:const EdgeInsets.all(16),children:[
      TextField(decoration:const InputDecoration(prefixIcon:Icon(Icons.search),labelText:'ابحث في أسماء الأسفار أو النص المعروض',border:OutlineInputBorder()),onChanged:(v)=>setState(()=>query=v)),
      const SizedBox(height:10),
      DropdownButtonFormField<int>(value:bookIndex,decoration:const InputDecoration(labelText:'السفر',border:OutlineInputBorder()),items:books.asMap().entries.map((e)=>DropdownMenuItem(value:e.key,child:Text((e.value as Map<String,dynamic>)['arabicName']?.toString()??(e.value as Map<String,dynamic>)['book']?.toString()??'سفر'))).toList(),onChanged:(v)=>setState(() { bookIndex=v??0; chapterIndex=0; })),
      const SizedBox(height:10),
      if(chapters.isNotEmpty) DropdownButtonFormField<int>(value:chapterIndex.clamp(0,chapters.length-1),decoration:const InputDecoration(labelText:'الإصحاح',border:OutlineInputBorder()),items:List.generate(chapters.length,(i)=>DropdownMenuItem(value:i,child:Text('${i+1}'))),onChanged:(v)=>setState(()=>chapterIndex=v??0)),
      const SizedBox(height:12),
      ...verses.where((v)=>query.isEmpty||((v as Map<String,dynamic>)['text']?.toString().toLowerCase().contains(query.toLowerCase())??false)).map((v){final verse=v as Map<String,dynamic>;return Card(color:Colors.white,child:Padding(padding:const EdgeInsets.all(12),child:Text('${verse['number']??''}. ${verse['text']??''}',style:const TextStyle(fontSize:17,height:1.8))));}),
    ]);
  }
}

class PrayerPage extends StatefulWidget { const PrayerPage({super.key}); @override State<PrayerPage> createState()=>_PrayerPageState(); }
class _PrayerPageState extends State<PrayerPage> {
  String hour='prime'; String watch='1';
  final hours=const {'prime':'صلاة باكر','terce':'صلاة الساعة الثالثة','sext':'صلاة الساعة السادسة','none':'صلاة الساعة التاسعة','vespers':'صلاة الغروب','compline':'صلاة النوم','midnight':'صلاة نصف الليل'};
  @override Widget build(BuildContext context)=>ListView(padding:const EdgeInsets.all(16),children:[
    const Text('الأجبية',style:TextStyle(fontSize:24,fontWeight:FontWeight.bold,color:navy)),
    const SizedBox(height:12),
    DropdownButtonFormField<String>(value:hour,decoration:const InputDecoration(labelText:'اختر الساعة',border:OutlineInputBorder()),items:hours.entries.map((e)=>DropdownMenuItem(value:e.key,child:Text(e.value))).toList(),onChanged:(v)=>setState(()=>hour=v??'prime')),
    if(hour=='midnight') DropdownButtonFormField<String>(value:watch,decoration:const InputDecoration(labelText:'الخدمة',border:OutlineInputBorder()),items:const [DropdownMenuItem(value:'1',child:Text('الخدمة الأولى')),DropdownMenuItem(value:'2',child:Text('الخدمة الثانية')),DropdownMenuItem(value:'3',child:Text('الخدمة الثالثة'))],onChanged:(v)=>setState(()=>watch=v??'1')),
    const SizedBox(height:12),
    FilledButton.icon(onPressed:()=>Navigator.push(context,MaterialPageRoute(builder:(_)=>DetailPage(title:hours[hour]!,path:hour=='midnight'?'/agpeya/midnight/watch/$watch':'/agpeya/$hour'))),icon:const Icon(Icons.download),label:const Text('عرض النص وحفظه تلقائيًا')),
    const SizedBox(height:10),
    const Text('النصوص التي تم تحميلها بنجاح تُحفظ على الجهاز وتُعرض عند انقطاع الإنترنت.',style:TextStyle(height:1.7,color:Colors.black54)),
  ]);
}

class ChurchPage extends StatelessWidget { const ChurchPage({super.key}); @override Widget build(BuildContext context)=>ListView(padding:const EdgeInsets.all(16),children:[
  const Text('الكنيسة والتقويم',style:TextStyle(fontSize:24,fontWeight:FontWeight.bold,color:navy)),
  const SizedBox(height:12),
  _item(context,'قراءات القطمارس',Icons.menu_book,'/readings/${DateTime.now().toIso8601String().substring(0,10)}?detailed=true'),
  _item(context,'السنكسار',Icons.event_note,'/synaxarium/${DateTime.now().toIso8601String().substring(0,10)}'),
  _item(context,'التسبحة السنوية',Icons.music_note,'/tasbeha/sunday?lang=ar'),
  _item(context,'الموسم الطقسي',Icons.calendar_month,'/season/${DateTime.now().toIso8601String().substring(0,10)}'),
  _item(context,'الصوم',Icons.restaurant,'/fasting/${DateTime.now().toIso8601String().substring(0,10)}'),
]); Widget _item(BuildContext c,String s,IconData i,String p)=>Card(color:Colors.white,child:ListTile(leading:Icon(i,color:gold),title:Text(s),trailing:const Icon(Icons.chevron_left),onTap:()=>Navigator.push(c,MaterialPageRoute(builder:(_)=>DetailPage(title:s,path:p)))));}

class NotesPage extends StatefulWidget { const NotesPage({super.key}); @override State<NotesPage> createState()=>_NotesPageState(); }
class _NotesPageState extends State<NotesPage> {
  final controller=TextEditingController(); List<String> notes=[];
  @override void initState(){super.initState();_load();}
  Future<void> _load()async{final p=await SharedPreferences.getInstance();if(mounted)setState(()=>notes=p.getStringList('kenoz_notes')??[]);}
  Future<void> _add()async{final s=controller.text.trim();if(s.isEmpty)return;final p=await SharedPreferences.getInstance();notes=[...notes,s];await p.setStringList('kenoz_notes',notes);controller.clear();if(mounted)setState((){});}
  @override void dispose(){controller.dispose();super.dispose();}
  @override Widget build(BuildContext context)=>Padding(padding:const EdgeInsets.all(16),child:Column(children:[
    const Text('ملاحظاتي الروحية',style:TextStyle(fontSize:24,fontWeight:FontWeight.bold,color:navy)),
    const SizedBox(height:12),TextField(controller:controller,maxLines:3,decoration:const InputDecoration(labelText:'اكتب ملاحظة أو تأملًا',border:OutlineInputBorder())),
    const SizedBox(height:8),Align(alignment:Alignment.centerLeft,child:FilledButton(onPressed:_add,child:const Text('حفظ'))),
    const Divider(),Expanded(child:notes.isEmpty?const Center(child:Text('لا توجد ملاحظات بعد.')):ListView.builder(itemCount:notes.length,itemBuilder:(c,i)=>Card(color:Colors.white,child:ListTile(title:Text(notes[i]),trailing:IconButton(icon:const Icon(Icons.delete_outline),onPressed:()async{notes.removeAt(i);final p=await SharedPreferences.getInstance();await p.setStringList('kenoz_notes',notes);if(mounted)setState((){});}))))),
  ]));
}

class DetailPage extends StatefulWidget { final String title,path; const DetailPage({super.key,required this.title,required this.path}); @override State<DetailPage> createState()=>_DetailPageState(); }
class _DetailPageState extends State<DetailPage> {
  dynamic data; bool loading=true,offline=false; String error='';
  @override void initState(){super.initState();_load();}
  Future<void> _load()async{
    setState(()=>loading=true);
    try{
      final uri=Uri.parse(widget.path.startsWith('http')?widget.path:'$apiRoot${widget.path.startsWith('/')?widget.path.substring(1):widget.path}');
      final result=await KenozApi.get('/${uri.path.split('/api/').last}',query:uri.queryParameters.isEmpty?null:uri.queryParameters);
      if(mounted)setState(() { data=result.data; offline=result.offline; });
    }catch(e){if(mounted)setState(()=>error='لم نتمكن من جلب هذا المحتوى ولا توجد نسخة محفوظة بعد. اتصل بالإنترنت وحاول مرة أخرى.');}
    finally{if(mounted)setState(()=>loading=false);}
  }
  @override Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:Text(widget.title)),body:loading?const Center(child:CircularProgressIndicator()):error.isNotEmpty?Center(child:Padding(padding:const EdgeInsets.all(24),child:Column(mainAxisSize:MainAxisSize.min,children:[const Icon(Icons.cloud_off,size:42,color:gold),const SizedBox(height:12),Text(error,textAlign:TextAlign.center),const SizedBox(height:12),FilledButton(onPressed:_load,child:const Text('إعادة المحاولة'))]))):Column(children:[
    Container(width:double.infinity,padding:const EdgeInsets.all(10),color:offline?const Color(0xFFFFF0D5):const Color(0xFFE3F4E8),child:Text(offline?'معروض من النسخة المحفوظة دون إنترنت':'تم التحميل — حُفظ تلقائيًا على الجهاز',textAlign:TextAlign.center)),
    Expanded(child:ListView(padding:const EdgeInsets.all(16),children:[_render(data)])),
  ]));
  Widget _render(dynamic v){
    if(v==null)return const SizedBox.shrink();
    if(v is Map){return Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:v.entries.map((e)=>Padding(padding:const EdgeInsets.only(bottom:8),child:Card(color:Colors.white,child:Padding(padding:const EdgeInsets.all(12),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text(_label(e.key.toString()),style:const TextStyle(fontWeight:FontWeight.bold,color:navy,fontSize:16)),const SizedBox(height:6),_render(e.value)]))))).toList());}
    if(v is List)return Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:v.map((x)=>Padding(padding:const EdgeInsets.only(bottom:6),child:_render(x))).toList());
    return SelectableText(v.toString(),style:const TextStyle(fontSize:16,height:1.7));
  }
  String _label(String s){const m={'vespers':'عشية','matins':'باكر','liturgy':'القداس','pauline':'البولس','catholic':'الكاثوليكون','praxis':'الإبركسيس','psalm':'المزمور','gospel':'الإنجيل','synaxarium':'السنكسار','readings':'القراءات','date':'التاريخ','title':'العنوان','text':'النص','content':'المحتوى','description':'التفاصيل','name':'الاسم','reference':'المرجع','season':'الموسم الطقسي','fasting':'الصوم','saints':'القديسون'};return m[s]??s.replaceAll('_',' ');}
}

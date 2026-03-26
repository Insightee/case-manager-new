
import { Employee, PayslipRecord } from '../types';

// Existing static data to preserve emails
const existingEmployees: Employee[] = [
  { employeeId: '1006', name: 'Anisha Kesarla', email: 'anisha.kesarla@gmail.com' },
  { employeeId: '1007', name: 'Amrapali Guha Majumder', email: 'amrapaligmajumder@gmail.com' },
  { employeeId: '1009', name: 'Balambal Ganesh', email: 'balambalganesh@gmail.com' },
  { employeeId: '1026', name: 'Chithra M', email: 'chithra.madhesh76@gmail.com' },
  { employeeId: '1032', name: 'Jessima Pastina', email: 'jessimapastina@gmail.com' },
  { employeeId: '1043', name: 'Krupa Mohan', email: 'krupamohan179@gmail.com' },
  { employeeId: '1050', name: 'Raajasi Godbole', email: 'raajasigodbole18@gmail.com' },
  { employeeId: '1053', name: 'Reeba Shaji', email: 'reebashaji2010@gmail.com' },
  { employeeId: '1061', name: 'Shaima Nathalia Dsa', email: 'dsashaimanathalia@gmail.com' },
  { employeeId: '1063', name: 'Sirisha SR', email: 'sirisha8299@gmail.com' },
  { employeeId: '1073', name: 'Thrisha Senthil', email: 'thrisha1999@gmail.com' },
  { employeeId: '1074', name: 'Ume Sabah', email: 'umesabah97@gmail.com' },
  { employeeId: '1079', name: 'Anusha Alva', email: 'anushaalva000@gmail.com' },
  { employeeId: '1082', name: 'Nikita Nath', email: 'nikitanath8@gmail.com' },
  { employeeId: '1112', name: 'Siri S. Kamath', email: 'siriskamath312000@gmail.com' },
  { employeeId: '1123', name: 'Divya Dogra', email: 'dividogra07@gmail.com' },
  { employeeId: '1126', name: 'Jayamaikodi S', email: 'jayamaikodiselvam@gmail.com' },
  { employeeId: '1145', name: 'Athira Thomas', email: 'athirathomas1998@gmail.com' },
  { employeeId: '1160', name: 'V Sahana', email: 'sahanaurs2303@gmail.com' },
  { employeeId: '1167', name: 'Aiswarya Rajeev', email: 'aiswaryarajeev19012001@gmail.com' },
  { employeeId: '1172', name: 'Faryal Fazal', email: 'faryalfazal18@gmail.com' },
  { employeeId: '1190', name: 'Michel Sandra', email: 'michel.sandra.ankita@gmail.com' },
  { employeeId: '1193', name: 'Aifha P', email: 'aifhapoolakkal@gmail.com' },
  { employeeId: '1208', name: 'Annsweeta James', email: 'annsweettajames@gmail.com' },
  { employeeId: '1210', name: 'Sukanya Tripathy', email: 'sukanya.tripathy27@gmail.com' },
  { employeeId: '1218', name: 'Tanvika Ellore', email: 'tanvikaellore20@gmail.com' },
  { employeeId: '1229', name: 'Brigetta Chakraborty', email: 'chakrabortybrigetta@gmail.com' },
  { employeeId: '1235', name: 'Ananya Chakroborty', email: 'chakrabortyananya887@gmail.com' },
  { employeeId: '1239', name: 'Bhavna Seervi', email: 'bhavnaseervi4@gmail.com' },
  { employeeId: '1251', name: 'Mrinalini Das', email: 'mrinalinidas2000@gmail.com' },
  { employeeId: '1257', name: 'Pratiti Das', email: 'pratitidas.slg@gmail.com' },
  { employeeId: '1262', name: 'Sarangi Krishna P', email: 'sarangikrishna02@gmail.com' },
  { employeeId: '1271', name: 'Ardra Luke Deedi', email: 'ardra.psy@gmail.com' },
  { employeeId: '1272', name: 'Arunashree S', email: 'anu.arunashree03@gmail.com' },
  { employeeId: '1277', name: 'Drisya Rajeev', email: 'drisyarajeev95@gmail.com' },
  { employeeId: '1278', name: 'Haridra Vivek', email: 'haridrathachodiyil@gmail.com' },
  { employeeId: '1279', name: 'Jeena Reji', email: 'jeena20577@gmail.com' },
  { employeeId: '1280', name: 'Mahak Rathi', email: 'mahak.rathi31@gmail.com' },
  { employeeId: '1287', name: 'Noora Ansar', email: 'nooraansar45@gmail.com' },
  { employeeId: '1288', name: 'Oindrila Bhattacharya', email: 'boindrila20@gmail.com' },
  { employeeId: '1307', name: 'Ankita Komath', email: 'ankitakomath0805@gmail.com' },
  { employeeId: '1309', name: 'Anupriyadharshini Kannan', email: 'anupriya2019k@gmail.com' },
  { employeeId: '1310', name: 'Arunima S Kumar', email: 'arunimasreekumar17@gmail.com' },
  { employeeId: '1313', name: 'Iqra Sadaf S', email: 'iqrasadaf11@gmail.com' },
  { employeeId: '1318', name: 'Safaniya A', email: 'safaniya2768@gmail.com' },
  { employeeId: '1321', name: 'Tintu James', email: 'tintujames850@gmail.com' },
  { employeeId: '1323', name: 'Bruno Vansio Mansio', email: 'brunovansio84@gmail.com' },
  { employeeId: '1325', name: 'Gayathri J', email: 'gayathrilekshmi07@gmail.com' },
  { employeeId: '1329', name: 'Sanika Anoop K', email: 'sanikaanoop@gmail.com' },
  { employeeId: '1331', name: 'Sandra Raj', email: 'sandrarajcs@gmail.com' },
  { employeeId: '1337', name: 'Binsha', email: 'bnshsalim@gmail.com' },
  { employeeId: '1339', name: 'Mariyam Shadin', email: 'shadin.mariyam@gmail.com' },
  { employeeId: '1344', name: 'Rachel George', email: 'rachelmariageorge20@gmail.com' },
  { employeeId: '1346', name: 'Santra Jacob', email: 'santramjacob@gmail.com' },
  { employeeId: '1348', name: 'Varsha H', email: 'varshah2002@gmail.com' },
  { employeeId: '1353', name: 'Anaswara P S', email: 'anaswaraps2000@gmail.com' },
  { employeeId: '1356', name: 'Divya G', email: 'divyajoshua369@gmail.com' },
  { employeeId: '1360', name: 'Madhu Shalini R S', email: 'madhushalinirs01@gmail.com' },
  { employeeId: '1364', name: 'Shruti Gupta', email: 'shrutiguptaa26@gmail.com' },
  { employeeId: '1366', name: 'Vaishnavi Ravindran', email: 'vr.vaish902@gmail.com' },
  { employeeId: '1369', name: 'Ekta Joshi', email: 'ektajoshi260@gmail.com' },
  { employeeId: '1370', name: 'Delta Varghese', email: 'deltavarghese22@gmail.com' },
  { employeeId: '1371', name: 'Eesha Borthakur', email: 'eeshaborthakur@gmail.com' },
  { employeeId: '1378', name: 'Spoorthi P', email: 'spoorthysarathy143@gmail.com' },
  { employeeId: '1385', name: 'Anagha A', email: 'anagha.ashwini@gmail.com' },
  { employeeId: '1386', name: 'Ayushi Pandey', email: 'ayushipandeyr5@gmail.com' },
  { employeeId: '1392', name: 'Shravani P', email: 'shravanisunu48@gmail.com' },
  { employeeId: '1394', name: 'Swetha Raj P.P', email: 'swethah111@gmail.com' },
  { employeeId: '1397', name: 'Sneha PS', email: 'snehasurendar001@gmail.com' },
  { employeeId: '1401', name: 'Nitya Chaitanya', email: 'nitya.chaitanya@outlook.com' },
  { employeeId: '1405', name: 'Hrithika Krishna', email: 'hrithika.hk19@gmail.com' },
  { employeeId: '1409', name: 'Athullya Philip', email: 'athullyahphilip@gmail.com' },
  { employeeId: '1415', name: 'Granthika M', email: 'granthikamanirao1611@gmail.com' },
  { employeeId: '1418', name: 'Neha Mariya', email: 'nehamary2000@gmail.com' },
  { employeeId: '1420', name: 'Akila Reddy', email: 'akilareddy50@gmail.com' },
  { employeeId: '1421', name: 'Sanjana Vijai', email: 'sanjanavijai21@gmail.com' },
  { employeeId: '1425', name: 'Ananya Sreedhar', email: 'ananyasreedhar001@gmail.com' },
  { employeeId: '1427', name: 'Hannah Jacob', email: 'hannahmelel30@gmail.com' },
  { employeeId: '1428', name: 'Sataparni', email: 'sataparni@gmail.com' },
  { employeeId: '1429', name: 'Manasvi Tyagi', email: 'manasvityagi24@gmail.com' },
  { employeeId: '1432', name: 'Rishu Singh', email: 'snehayadava23@gmail.com' },
  { employeeId: '1433', name: 'Priyadarshini', email: 'priyadarshini11199902@gmail.com' },
  { employeeId: '1437', name: 'Sudeepti Pillai', email: 'sudeeptipillai@gmail.com' },
  { employeeId: '1438', name: 'Traidha Majumdar', email: 'therapywithtraidha@gmail.com' },
  { employeeId: '1439', name: 'Varna Unni', email: 'varnaunni12@gmail.com' },
  { employeeId: '1441', name: 'Badhriya M', email: 'badhriyaibrahim18@gmail.com' },
  { employeeId: '1442', name: 'Abiya Susan Tojo', email: 'abiyasusantojo@gmail.com' },
  { employeeId: '1443', name: 'Ardra Saju', email: 'ardrasaju2003@gmail.com' },
  { employeeId: '1444', name: 'Anagha Regi', email: 'anaghareji000@gmail.com' },
  { employeeId: '1445', name: 'Aryalakshmi Krishnakumar', email: 'aryalakshmicool1996@gmail.com' },
  { employeeId: '1448', name: 'Deepali Pradeep', email: 'deepalipradeep910@gmail.com' },
  { employeeId: '1449', name: 'Jeneepeaceful lawphniaw', email: 'jeneepeaceful2023@gmail.com' },
  { employeeId: '1451', name: 'Namratha N', email: 'ninamrathanl@gmail.com' },
  { employeeId: '1452', name: 'Niharika Aswani', email: 'niharikaaswani7@gmail.com' },
  { employeeId: '1454', name: 'Priscilla', email: 'priscilla17726@gmail.com' },
  { employeeId: '1455', name: 'Priyanka MK', email: 'priyankamk662@gmail.com' },
  { employeeId: '1456', name: 'Rasika', email: 'rasika.sri1182@gmail.com' },
  { employeeId: '1457', name: 'Sneha Yohanan', email: 'snehayohannan1920@gmail.com' },
  { employeeId: '1458', name: 'Sona Saji', email: 'sonasaji15116@gmail.com' },
  { employeeId: '1459', name: 'Vaishnavi Patra', email: 'vaishnavipatra6@gmail.com' },
  { employeeId: '1460', name: 'Visnupriya', email: 'priyavisnu45@gmail.com' },
  { employeeId: '1467', name: 'Shivangi agarwal', email: 'shivangi.agarwal0906@gmail.com' },
  { employeeId: '1471', name: 'Aleena shiby', email: 'aleenashiby25@gmail.com' },
  { employeeId: '1472', name: 'Misiriya k', email: 'rinumisriya112@gmail.com' },
  { employeeId: '1473', name: 'Sriparna Paul', email: 'sriparnapaul611@gmail.com' },
  { employeeId: '1475', name: 'Shravya S', email: 'sraishravya@gmail.com' },
  { employeeId: '1476', name: 'Gudla prathyusha', email: 'prathyushar77@gmail.com' },
  { employeeId: '1477', name: 'Aparna Choudhary', email: 'aparnachoudhary166@gmail.com' },
  { employeeId: '1478', name: 'Kashish Kumar', email: 'kashishkumar4008@gmail.com' },
  { employeeId: '1479', name: 'Ananya Sharma', email: 'ananyasharma041002@gmail.com' },
  { employeeId: '1480', name: 'Anaswara Maria Paul', email: 'anaswaramariapaul@gmail.com' },
  { employeeId: '1481', name: 'Anuradha Koch', email: 'kochanuradha318@gmail.com' },
  { employeeId: '1482', name: 'Dhvani Manchanda', email: 'dhvanimanchanda@gmail.com' },
  { employeeId: '1483', name: 'Dinky Tejwani', email: 'reachdinkytejwani@gmail.com' },
  { employeeId: '1484', name: 'Kalpana G', email: 'kalpanagurumurthy123@gmail.com' },
  { employeeId: '1486', name: 'Linette John', email: 'linettejohn203@gmail.com' },
  { employeeId: '1487', name: 'Nehal Mathur', email: 'nehal.mathur2002@gmail.com' },
  { employeeId: '1488', name: 'Nivita Jain', email: 'nivitaajain@gmail.com' },
  { employeeId: '1489', name: 'Oindrila Dutta', email: 'oindriladutta37@gmail.com' },
  { employeeId: '1492', name: 'Riya Thomas', email: 'thomasriya590@gmail.com' },
  { employeeId: '1494', name: 'Varshika', email: 'varshikavenkatakrishnan@gmail.com' },
  { employeeId: '1495', name: 'Janhavi M', email: 'janhavijanu13@gmail.com' },
  { employeeId: '1496', name: 'Vaishnavi M Mulgund', email: 'vaishnavi.mulgund@gmail.com' },
  { employeeId: '1497', name: 'Muskaan Jain', email: 'muskaan.jain291@gmail.com' },
  { employeeId: '1498', name: 'Rinedha Raman', email: 'rinedharahman@gmail.com' },
  { employeeId: '1499', name: 'Sonakshi Datta', email: 'sonakshichocopie@gmail.com' },
  { employeeId: '1502', name: 'Komal Munesh', email: 'komalmunesh1552@gmail.com' },
  { employeeId: '1505', name: 'Ankita Ghosh', email: 'mailghoshankita@gmail.com' },
  { employeeId: '1506', name: 'Veena S', email: 'veenarsraghu300@gmail.com' },
  { employeeId: '1509', name: 'Nikhat sherief', email: 'nikhatsheriefba@gmail.com' },
  { employeeId: '1510', name: 'Subidsha', email: 'jegadeesansubi@gmail.com' },
  { employeeId: '1512', name: 'Gowri Nanda', email: 'gowrinandana728@gmail.com' },
  { employeeId: '1514', name: 'Sunidhi S G', email: 'sunidhisg4@gmail.com' },
  { employeeId: '1515', name: 'Ria Varghese', email: 'ria.vrgs17@gmail.com' },
  { employeeId: '1516', name: 'Barasha Nasim', email: 'nasimbarasha@gmail.com' },
  { employeeId: '1517', name: 'Deva Dharshini', email: 'devadharshini650@gmail.com' },
  { employeeId: '1518', name: 'Pooja Prabakaran', email: 'poojaprabhakaranb1617@gmail.com' },
  { employeeId: '1519', name: 'Akshaya R', email: 'akshayamyy12@gmail.com' },
  { employeeId: '1520', name: 'Nikita Badgujar', email: 'nikhatsheriefba@gmail.com' },
  { employeeId: '1522', name: 'Manal Razak', email: 'manalrazak7@gmail.com' },
  { employeeId: '1523', name: 'Zeba Ahmad', email: 'zebaa3591@gmail.com' },
  { employeeId: '1526', name: 'Ann Mary John', email: 'annmaryjohn28@gmail.com' },
  { employeeId: '1527', name: 'Luann', email: 'luannvosto@gmail.com' },
  { employeeId: '1534', name: 'Ann Maria Jose', email: 'annmariaj311@gmail.com' },
  { employeeId: '1535', name: 'Jenifer. K', email: 'jenifer.k1017@gmail.com' },
  { employeeId: '1536', name: 'Lima pandey', email: 'limapandey1@gmail.com' },
  { employeeId: '1537', name: 'Renita Jhonson', email: 'renitajohnson2108@gmail.com' },
  { employeeId: '1538', name: 'Balkirat Kaur', email: 'balki2275@gmail.com' },
  { employeeId: '1539', name: 'Sandhra maria johnson', email: 'sandramjohn03@gmail.com' },
  { employeeId: '1540', name: 'Sannidhi Nayak', email: 'sannidhi1404@gmail.com' },
  { employeeId: '1541', name: 'Anusha HV', email: 'aanushahv945@gmail.com' },
  { employeeId: '1542', name: 'Sri Sanju P S', email: 'srisanjusaravanan@gmail.com' },
  { employeeId: '1543', name: 'Babitha P P', email: 'babi31dec@gmail.com' },
  { employeeId: '1544', name: 'Abhirami P R', email: 'abhiramipr71@gmail.com' },
  { employeeId: '1545', name: 'Anthea Manuual', email: 'antheamanuel@gmail.com' },
  { employeeId: '1547', name: 'Hema R', email: 'hemaofficial002@gmail.com' },
  { employeeId: '1548', name: 'Hridhya Sudheer', email: 'hridyasudheer54@gmail.com' },
  { employeeId: '1550', name: 'Nivedita Sri', email: 'niveditalakshu@gmail.com' },
  { employeeId: '1552', name: 'Tania Felix', email: 'tanialisetta10@gmail.com' },
  { employeeId: '1556', name: 'Nandana Rakesh', email: 'nandanarakesh107@gmail.com' },
  { employeeId: '1559', name: 'P. S. Arathi', email: 'aarathii.p.s@gmail.com' },
  { employeeId: '1560', name: 'Jeffy J Mathew', email: 'jeffymathewpj@gmail.com' },
  { employeeId: '1562', name: 'Rinsha Rasheed K R', email: 'rinsha0466@gmail.com' },
  { employeeId: '1563', name: 'Fathimath Rafna', email: 'excelrafna@gmail.com' },
  { employeeId: '1564', name: 'Mapratha. R', email: 'maprathar@gmail.com' },
  { employeeId: '1565', name: 'Meenakshy S', email: 'meenakshisr22@gmail.com' },
  { employeeId: '1567', name: 'Kezia Susan Benison', email: 'keziasusben@gmail.com' },
  { employeeId: '1568', name: 'Saalini P Chandran', email: 'saalinipchandran@gmail.com' },
  { employeeId: '1569', name: 'Namitha. P', email: 'namithap1000@gmail.com' },
  { employeeId: '1570', name: 'Nehal Bauskar', email: 'bauskarnehal25@gmail.com' },
  { employeeId: '1571', name: 'Sneha raj m.v', email: 'sneharajmv2002@gmail.com' },
  { employeeId: '1572', name: 'Panchami Nanjundaiah', email: 'panchamikumar01@gmail.com' },
  { employeeId: '1574', name: 'Isha Shri', email: 'ishasnath@gmail.com' },
  { employeeId: '1575', name: 'Sree Aburva R', email: 'sreeaburvaradhakrishnan@gmail.com' },
  { employeeId: '1576', name: 'Anagha K', email: 'anaghakapz2014127@gmail.com' },
  { employeeId: '1577', name: 'Nathania Srushti Puran Sing', email: 'singhnathania@gmail.com' },
  { employeeId: '1578', name: 'Rashi Sharma', email: 'thebuddingtherapist0.2@gmail.com' },
  { employeeId: '1579', name: 'Gayathri v Binu', email: 'gayathrivbinu@gmail.com' },
  { employeeId: '1580', name: 'Raksha D', email: 'chandwaniraksha@gmail.com' },
  { employeeId: '1581', name: 'Noufeera.k', email: 'noufiramusthafa19@gmail.com' },
  { employeeId: '1582', name: 'Marissa Ruth Furtado', email: 'marissafurtado77@gmail.com' },
  { employeeId: '1583', name: 'Kunjala lyer', email: 'kunjalaiyer25@gmail.com' },
  { employeeId: '1584', name: 'S P Shalini', email: 'shalinisivan23@gmail.com' },
  { employeeId: '1585', name: 'Kriti Basu', email: 'kriti1391@gmail.com' },
  { employeeId: '1586', name: 'Eloa Gladis', email: 'gladiseloa@gmail.com' },
  { employeeId: '1587', name: 'Deeksha Raj', email: 'deeksshanagaraj@gmail.com' },
  { employeeId: '1588', name: 'Aishwarya Murthy', email: 'aishumurthy7@gmail.com' },
  { employeeId: '1591', name: 'Abirami Siddheshwar Khara', email: 'abiramik1207@gmail.com' },
  { employeeId: '1592', name: 'Prarthana Mazumdar', email: 'prarthanamazumdar08@gmail.com' },
  { employeeId: '1593', name: 'Pratheeksha Satheesh', email: 'pratheeksha.therapy@gmail.com' },
  { employeeId: '1596', name: 'Amrutha C', email: 'amruthapoolot3@gmail.com' },
  { employeeId: '1597', name: 'Kanikha k', email: 'kanikhak29@gmail.com' },
  { employeeId: '1598', name: 'Amitha Joseph', email: 'amithajosephp0000@gmail.com' },
  { employeeId: '1599', name: 'Adale Chewang', email: 'adahachewang67370@gmail.com' },
  { employeeId: '1603', name: 'Misbah Fasihuddin', email: 'misbahfasihuddin2002@gmail.com' },
  { employeeId: '1604', name: 'Niroosha chandra', email: 'nirooshachandr@gmail.com' },
  { employeeId: '1605', name: 'Ruchitha A', email: 'ruchithareddy8898@gmail.com' },
  { employeeId: '1606', name: 'Suprabha GM', email: 'gmsuprabha25@gmail.com' },
  { employeeId: '1607', name: 'shradha menon', email: 'sradhamenon29@gmail.com' },
  { employeeId: '1608', name: 'Bhoomika M', email: 'bhoomikam26@gmail.com' },
  { employeeId: '1609', name: 'Trisha P', email: 'trisha.pasupathy@gmail.com' },
  { employeeId: '1610', name: 'Rakshata Balachandra Salg', email: 'rakshatasalgundi@gmail.com' },
  { employeeId: '1612', name: 'Safia PS', email: 'safiapsjobs25@gmail.com' },
  { employeeId: '1613', name: 'Divya Nayana Ratakonda', email: 'nayanaweb.03@gmail.com' },
  { employeeId: '1614', name: 'Neimenuo Chadi', email: 'neimechadi@gmail.com' },
  { employeeId: '1615', name: 'Nazia Fathima S', email: 'fathimanazia0907@gmail.com' },
  { employeeId: '1616', name: 'P. Srinithi', email: 'srinithipandi78@gmail.com' },
  { employeeId: '1618', name: 'Josmy Joseph', email: 'josmyjoseph5241@gmail.com' },
  { employeeId: 'EMP999', name: 'Midhun Noble', email: 'midhunnoble@gmail.com' },
];

// Raw Text Data to be parsed (Simulating Database)
const rawDec2024 = `
1006 Anisha Kesarla 52710 5271 47439
1048 Praneesha 6000 600 5400
1415 Granthika 7333 733 6600
1438 Traidha Majumdar 25000 2500 22500
1455 Priyanka MK 5367 537 4830
1508 Hansika Anand 23000 2300 20700
1515 Ria Vargese 10833 1083 9750
1560 Jeffy 11100 1110 9990
1007 Amrapali Guha Majumder 8400 840 7560
1009 Balambal Ganesh 70785 7079 63707
1026 Chithra M 24200 2420 21780
1032 Jessima Pastina 20542 2054 18488
1043 Krupa Mohan 54500 5450 49050
1050 Raajasi Godbole 46520 4652 41868
1053 Reeba Shaji 46200 4620 41580
1061 Shaima Nathalia Dsa 27246 2725 24521
1063 Sirisha SR 42000 4200 37800
1073 Thrisha Senthil 21110 2111 18999
1074 Ume Sabah 35778 3578 32200
1079 Anusha Alva B 81174 8117 73056
1082 Nikita Nath 16550 1655 14895
1112 Siri S. Kamath 61680 6168 55512
1123 Divya Dogra 46000 4600 41400
1126 Jayamaikodi S. 41033 4103 36930
1145 Athira Thomas 25000 2500 22500
1160 V Sahana 43653.33 4365 39288
1167 Aiswarya Rajeev 50740 5074 42030
1172 Faryal Fazal 32852 3285 29567
1180 Vijayashri A. 7700 770 6930
1190 Michel Sandra 42400 4240 38160
1193 Aifha P 41800 4180 37620
1208 Annsweetta James 19000 1900 17100
1210 Sukanya Tripathy 21927 2193 19734
1218 Tanvika Ellore 29200 2920 26280
1229 Brigetta Chakraborty 36767 3677 33090
1235 Ananya Chakroborty 25000 2500 22500
1239 Bhavna Seervi 30400 3040 27360
1251 Mrinalini Das 24167 2417 21750
1257 Pratiti Das 37000 3700 33300
1262 Sarangi Krishna P. 38400 3840 34560
1271 Ardra Luke Deedi 25000 2500 22500
1272 Arunashree S 35920 3592 32328
1277 Drisya Rajeev 38800 3880 34920
1278 Haridra Vivek 29767 2977 26790
1279 Jeena Reji 24167 2417 21750
1280 Mahak Rathi 44300 4430 39870
1288 Oindrila Bhattacharya 40100 4010 36090
1307 Ankita Komath 22000 2200 19800
1309 Anupriyadharshini Kannan 37200 3720 33480
1310 Arunima S. Kumar 31400 3140 28260
1313 Iqra Sadaf S. 25000 2500 22500
1318 Safaniya A 30567 3057 27510
1321 Tintu James 26000 2600 23400
1323 Bruno Vansio Mansio J 34800 3480 31320
1329 Sanika Anoop K. 28615 2861 25753
1331 Sandra Raj 35800 3580 32220
1337 Binsha 34400 3440 30960
1339 Mariyam Shadin 42800 4280 38520
1344 Rachel George 24200 2420 21780
1346 Santra Jacob 29480 2948 26532
1348 Varsha H. 39500 3950 35550
1353 Anaswara PS 27033 2703 24330
1356 Divya G. 26400 2640 23760
1360 Madhu Shalini R S 27480 2748 24732
1364 Shruti Gupta 25000 2500 22500
1366 Vaishnavi Ravindran 27370 2737 24633
1369 Ekta Joshi 20000 2000 18000
1371 Eesha Borthakur 40600 4060 36540
1378 Spoorthi P 23667 2367 21300
1385 Anagha A. 25000 2500 22500
1386 Ayushi Pandey 22500 2250 20250
1392 Shravani P 30200 3020 27180
1394 Swetha Raj P.P 23000 2300 20700
1397 Sneha PS 26800 2680 24120
1401 Nitya Chaitanya 22000 2200 19800
1405 Hrithika Krishna 34800 3480 31320
1409 Athullya Philip 22000 2200 19800
1418 Neha Mariya 22233 2223 20010
1420 Akila Reddy 23000 2300 20700
1421 Sanjana Vijai 18667 1867 16800
1425 Ananya Sreedhar 30200 3020 27180
1427 Hannah Jacob 31160 3116 28044
1428 Sataparni 25000 2500 22500
1429 Manasvi Tyagi 32420 3242 29178
1432 Rishu Singh 18000 1800 16200
1433 Priyadarshini 19500 1950 17550
1437 Sudeepti Pillai 26200 2620 23580
1439 Varna Unni 23000 2300 20700
1441 Badhriya M 25000 2500 22500
1442 Abiya Susan Tojo 25000 2500 22500
1443 Ardra Saju 25400 2540 22860
1444 Anagha Reji 27000 2700 24300
1445 Aryalakshmi Krishnakumar 23000 2300 20700
1448 Deepali Pradeep 21250 2125 19125
1449 Jeneepeaceful Iawphniaw 23000 2300 20700
1451 Namratha N 29200 2920 26280
1454 Priscilla 25260 2526 22734
1456 Rasika 25000 2500 22500
1457 Sneha Yohanan 23000 2300 20700
1458 Sona Saji 23000 2300 20700
1459 Vaishnavi Patra 17400 1740 15660
1460 Visnupriya 23000 2300 20700
1465 Prachi Patel 25000 2500 22500
1467 Shivangi Agarwal 23591 2359 21232
1471 Aleena Shiby 21467 2147 19320
1472 Misiriya K 22233 2223 20010
1473 Sriparna Paul 31300 3130 28170
1475 Shravya S 23000 2300 20700
1476 Gudla Prathyusha 4400 440 3960
1477 Aparna Choudhary 23000 2300 20700
1479 Ananya Sharma 22233 2223 20010
1480 Anaswara Maria Paul 23000 2300 20700
1481 Anuradha Koch 20000 2000 18000
1482 Dhvani Manchanda 27260 2726 24534
1483 Dinky Tejwani 39600 3960 35640
1484 Kalpana G 20000 2000 18000
1486 Linette John 23000 2300 20700
1487 Nehal Mathur 22500 2250 20250
1488 Nivita Jain 20000 2000 18000
1489 Oindrila Dutta 37000 3700 33300
1492 Riya Thomas 23000 2300 20700
1494 Varshika 24167 2417 21750
1495 Janhavi M 25000 2500 22500
1496 Vaishnavi M Mulgund 23000 2300 20700
1497 Muskaan Jain 19333 1933 17400
1498 Rinedha Raman 19333 1933 17400
1499 Sonakshi Datta 25000 2500 22500
1502 Komal Munesh 24633 2463 22170
1505 Ankita Ghosh 20000 2000 18000
1506 Veena S 13000 1300 11700
1509 Nikhat Sherief 18167 1817 16350
1510 Subidsha 22500 2250 20250
1512 Gowri Nanda 23000 2300 20700
1514 Sunidhi S G 24167 2417 21750
1516 Barasha Nasim 19833 1983 17850
1517 Deva Dharshini 31367 3137 28230
1518 Pooja Prabakaran 27267 2727 24540
1519 Akshaya R 25000 2500 22500
1520 Nikita Bajugar 37600 3760 33840
1522 Manal Razak 22500 2250 20250
1523 Zeba Ahmad 20000 2000 18000
1526 Ann Mary John 20000 2000 18000
1527 Luann 23000 2300 20700
1534 Ann Maria Jose 20000 2000 18000
1535 Jenifer K 20000 2000 18000
1537 Renita Jhonson 14500 1450 13050
1538 Balkirat Kaur 27033 2703 24330
1539 Sandhra Maria Johnson 25000 2500 22500
1540 Sannidhi Nayak 34113 3411 30702
1541 Anusha HV 20000 2000 18000
1542 Sri Sanju P S 21800 2180 19620
1544 Abhirami P R 14500 1450 13050
1545 Anthea Manuual 1800 180 1620
1547 Hema R 20000 2000 18000
1548 Hridya Sudheer 25000 2500 22500
1550 Nivedita Sri 22500 2250 20250
1552 Tania Felix 20000 2000 18000
1556 Nandana Rakesh 24000 2400 21600
1559 P. S. Arathi 19333 1933 17400
1563 Fathimath Rafna 20000 2000 18000
1564 Mapratha R 16900 1690 15210
1565 Meenakshy S 23200 2320 20880
1567 Kezia Susan Benison 22233 2223 20010
1568 Saalini P Chandran 25000 2500 22500
1569 Namitha P 23000 2300 20700
1570 Nehal Bauskar 20000 2000 18000
1571 Sneha Raj M V 23000 2300 20700
1572 Panchami Nanjundaiah 15542 1554 13988
1574 Isha Shri 20000 2000 18000
1575 Sree Aburva R 24800 2480 22320
1576 Anagha K 23000 2300 20700
1577 Nathania Singh 23200 2320 20880
1578 Rashi Sharma 20000 2000 18000
1579 Gayathri V Binu 25000 2500 22500
1581 Noufeera K 19333 1933 17400
1582 Marissa Ruth Furtado 25000 2500 22500
1583 Kunjala Iyer 18000 1800 16200
1584 S P Shalini 22400 2240 20160
1585 Kriti Basu 24000 2400 21600
1586 Eloa Gladis 19500 1950 17550
1587 Deeksha Raj 17167 1717 15450
1588 Aishwarya Murthy 20000 2000 18000
1592 Prarthana Mazumdar 21733 2173 19560
1593 Pratheeksha Satheesh 24167 2417 21750
1596 Amrutha C 20000 2000 18000
1597 Kanikha K 25000 2500 22500
1598 Amitha Joseph 21000 2100 18900
1599 Adale Chewang 23000 2300 20700
1603 Misbah Fasihuddin 28800 2880 25920
1604 Niroosha Chandra 25000 2500 22500
1605 Ruchitha A 20000 2000 18000
1606 Suprabha GM 23000 2300 20700
1607 Sradha Menon 29000 2900 26100
1608 Bhoomika M 25000 2500 22500
1609 Trisha P 24000 2400 21600
1610 Rakshata Balachandra Salgundi 23000 2300 20700
1612 Safia PS 24000 2400 21600
1613 Divya Nayana Ratakonda 25000 2500 22500
1614 Neimenuo Chadi 24000 2400 21600
1615 Nazia Fathima S 25000 2500 22500
1616 P Srinithi 22500 2250 20250
1617 Rani Ganjave 25000 2500 22500
1619 Shehina Shan A 23000 2300 20700
1620 Rashi Pundhir 16300 1630 14670
1621 Varshini Selvakumar 25000 2500 22500
1622 Princy Immaculate 11400 1140 10260
1623 Nishitha Oruganti 20000 2000 18000
1624 Sneha Latha K 30000 3000 27000
1625 Rupika R Alyembyan 22233 2223 20010
1626 Sneha K P 23000 2300 20700
1627 Meghana R 25000 2500 22500
1628 Meghana R S 12667 1267 11400
1629 K K Srividya 15333 1533 13800
1630 Prerna Sisodia 25000 2500 22500
1631 Ngawang Saldon 23000 2300 20700
1632 Kavya P 6133 613 5520
1633 Simran Jagdal 5367 537 4830
1634 Sindhu A 8800 880 7920
1635 Fiza Akbar 5833 583 5250
1636 Pavani S 5833 583 5250
1017 Epahi 40000 4000 36000
1061 Shaima 40000 4000 36000
1081 Meghana Ravikumar 45000 0 45000
1082 Nikita Nath 50000 1000 69000
1084 Navya 60000 0 56000
1085 Bindiya Shajith 50000 5000 45000
1118 Harshada Sukale 40000 0 29333
1221 Pragya Dwivedi 45000 0 45000
1280 Mahak 15000 1500 13500
1322 Janani Krishnakumar 45000 0 45000
1358 Shilpa Noble 50000 5000 45000
1381 Poornima Rao 27000 2700 24300
1389 Pooja 30000 3000 27000
1406 Sanjivani 30000 3000 27000
1408 Nicky 100000 2000 98000
1412 Krishnapriya 40000 4000 36000
1421 Sanjana 15000 1500 13500
1546 Devika 25000 2500 22500
1551 Rohitt 15000 1500 13500
1599 Adale 15000 1500 13500
1600 Arvin 35000 3833 30450
1601 Sagar 16000 1600 14400
1602 Lakshmi 30000 2700 24300
1653 Trisha Biswas 14567 1457 13110
1654 Anushka Joshi 12667 1267 11400
1655 Rakhshaan Shamoodah 8433 843 7590
1656 Adiba Kalimi 9200 920 8280
1657 Sumitha P 8000 800 7200
1658 Kirti Tiwari 10833 1083 9750
1660 Chandana S 15000 1500 13500
1664 Aashlin Elizabeth A 11500 1150 10350
1494 Varshika 16666 1667 14999
1364 Shruti gupta 16666 1667 14999
1032 jessima 8333 833 7500
1366 Vaishnavi Ravindran 4167 417 3750
1488 Nivita 3667 367 3300
1659 Priyadharshini 9967 997 8970
1640 Chetana 8666 867 7799
1481 Anuradha Koch 10666 1067 9599
1661 Vinothini 2500 250 2250
1210 Sukanya Tripathy 21926 2193 19733
`;

const rawJan2025 = `
1085 Bindiya Shajith 50000 5000 45000
1627 Meghana R 45000 45000
1221 Pragya D 45000 45000
1322 Janani 45000 45000
1408 Nicky 100000 2000 98000
1412 Krishnapriya 40000 4000 36000
1406 Sanjivani 30000 3000 27000
1358 Shilpa 50000 5000 45000
1595 Poornima 27000 2700 24300
1082 Nikita 60000 64200
1017 Epahi 40000 4000 36000
1546 Devika 25000 2500 22500
1551 rohitt 15000 1500 13500
1599 Adale 15000 1500 13500
1280 Mahak 20850 2085 18765
1663 Kashvi 40000 4000 36000
1600 Arvin 35000 3500 31500
1061 Shaima 40000 4000 36000
1602 Lakshmi 30000 3000 27000
1389 Pooja Y 30000 3000 32580
1601 Sagar 15000 1500 13500
1421 Sanjana 16000 1600 14400
1647 noori 20000 2000 18000
1006 Anisha Kesarla 50030 5003 45027
1007 Amrapali Guha Majumder 18200 1820 16380
1009 Balambal Ganesh 52024 5202 46822
1026 Chithra M 24200 2420 21780
1043 Krupa Mohan 68410 6841 61569
1050 Raajasi Godbole 65510 6551 58959
1053 Reeba Shaji 35500 3550 31950
1061 Shaima Nathalia Dsa 28966 2897 26069
1063 Sirisha SR 56580 5658 50922
1073 Thrisha Senthil 22374 2237 20137
1074 Ume sabah 33048 3305 29743
1079 Anusha Alva B 80811 8081 72729
1082 Nikita Nath 31240 3124 28116
1112 Siri S. Kamath 62290 6229 56061
1123 Divya Dogra 42600 4260 38340
1126 Jayamaikodi S. 37533 3753 33780
1145 Athira Thomas 25000 2500 22500
1160 V Sahana 52260 5226 47034
1167 Aiswarya Rajeev 51223 5122 46101
1172 Faryal Fazal 41292 4129 37163
1473 Sriparna paul 32200 3220 28980
1180 Vijayashri A. 16800 1680 15120
1190 Michel Sandra 50060 5006 45054
1193 Aifha P 43480 4348 39132
1208 Annsweeta James 21800 2180 19620
1210 Sukanya Tripathy 3373 337 3036
1218 Tanvika Ellore 29620 2962 26658
1229 Brigetta Chakraborty 33967 3397 30570
1235 Ananya Chakroborty 25000 2500 22500
1239 Bhavna Seervi 31767 3177 28590
1251 Mrinalini Das 23333 2333 21000
1257 Pratiti Das 39100 3910 35190
1262 Sarangi Krishna P 38400 3840 34560
1271 Ardra luke deedi 26680 2668 24012
1272 Arunashree S 35920 3592 32328
1277 Drisya Rajeev 41100 4110 36990
1278 Haridra Vivek 25000 2500 22500
1278 Haridra Vivek 1400 140 1260
1279 Jeena Reji 25000 2500 22500
1280 Mahak Rathi 23220 2322 20898
1287 Noor Maryam 3333 333 3000
1287 Noora Ansar 25000 2500 22500
1288 Oindrila Bhattacharya 44020 4402 39618
1307 Ankita Komath 22000 2200 19800
1309 Anupriyadharshi ni Kannan 37200 3720 33480
1310 Arunima S. Kumar 30200 3020 27180
1313 Iqra Sadaf S. 27500 2750 24750
1318 Safaniya A 23000 2300 20700
1321 Tintu James 26000 2600 23400
1323 Bruno Vansio Mansio 26900 2690 24210
1325 Gayatri J 27500 2750 24750
1329 Sanika Anoop K. 31537 3154 28383
1331 Sandra Raj 27400 2740 24660
1337 Binsha 42900 4290 38610
1339 Mariyam Shadin 42800 4280 38520
1344 Rachel George 24200 2420 21780
1346 Santra Jacob 34967 3497 31470
1348 Varsha H. 40700 4070 36630
1353 Anaswara PS 25700 2570 23130
1356 Divya G. 26400 2640 23760
1360 Madhu Shalini R S 20840 2084 18756
1369 Ekta Joshi 20000 2000 18000
1371 Eesha Borthakur 35300 3530 31770
1378 Spoorthi P 26800 2680 24120
1385 Anagha A. 25000 2500 22500
1386 Ayushi Pandey 23000 2300 20700
1392 Shravani P 35000 3500 31500
1394 Swetha Raj P.P 23000 2300 20700
1397 Sneha P S 4800 480 4320
1397 Sneha PS 22000 2200 19800
1401 Nitya Chaitanya 20533 2053 18480
1405 Hrithika Krishna 36200 3620 32580
1409 Athullya Philip 18700 1870 16830
1418 Neha Mariya 23000 2300 20700
1420 Akila Reddy 23000 2300 20700
1421 Abirami Siddheshwar Kharatmal 17333 1733 15600
1425 Ananya Sreedhar 29433 2943 26490
1427 Hannah Jacob 26800 2680 24120
1428 Sataparni 25000 2500 22500
1429 Manasvi Tyagi 20000 2000 18000
1432 Rishu Singh 17400 1740 15660
1433 Priyadarshini 20000 2000 18000
1437 Sudeepti Pillai 25000 2500 22500
1439 Varna Unni 29433 2943 26490
1441 Badhriya M 25000 2500 22500
1443 Ardra Saju 23000 2300 20700
1444 Anagha Regi 24967 2497 22470
1449 Jeneepeaceful Iawphniaw 26000 2600 23400
1451 Namratha N 30400 3040 27360
1452 Niharika Aswani 8800 880 7920
1454 Priscilla 36560 3656 32904
1456 Rasika 40000 4000 36000
1457 Sneha Yohanan 23000 2300 20700
1458 Sona Saji 22233 2223 20010
1459 Vaishnavi Patra 17400 1740 15660
1460 Visnupriya 21467 2147 19320
1465 Prachi patel 25000 2500 22500
1467 Shivangi agarwal 23000 2300 20700
1471 Aleena shiby 22233 2223 20010
1472 Misiriya k 23000 2300 20700
1473 Sriparna paul 32200 3220 28980
1475 Shravya S 23000 2300 20700
1477 Aparna Choudhary 23000 2300 20700
1479 Ananya Sharma 23000 2300 20700
1480 Anaswara Maria Paul 22233 2223 20010
1481 Anuradha Koch 19333 1933 17400
1482 Dhvani Manchanda 27260 2726 24534
1483 Dinky Tejwani 39600 3960 35640
1484 Kalpana G 20000 2000 18000
1486 Linette John 23000 2300 20700
1487 Nehal Mathur 25000 2500 22500
1489 Oindrila Dutta 23250 2325 20925
1492 Riya Thomas 23000 2300 20700
1495 Janhavi M 14167 1417 12750
1496 Vaishnavi M Mulgund 30200 3020 27180
1497 Muskaan Jain 19333 1933 17400
1498 Rinedha Raman 20000 2000 18000
1499 Sonakshi Datta 24167 2417 21750
1502 Komal Munesh 26000 2600 23400
1508 Hansika Anand 25000 2500 22500
1512 Gowri Nandana 23000 2300 20700
1514 Sunidhi S G 25000 2500 22500
1517 Deva Dharshini 29800 2980 26820
1518 Pooja Prabakaran 25000 2500 22500
1519 Akshaya R 25000 2500 22500
1520 Nikita Badgujar 50800 5080 45720
1522 Manal Razak 23000 2300 20700
1523 Zeba Ahmad 23600 2360 21240
1526 Ann Mary John 20000 2000 18000
1527 Luann Vosto 18898 1890 17009
1534 Ann Maria Jose 20000 2000 18000
1535 Jenifer. K 20000 2000 18000
1537 Renita Jhonson 15000 1500 13500
1538 Balkirat Kaur 30200 3020 27180
1539 Sandhra Maria Johnson 25000 2500 22500
1540 Sannidhi Nayak 39200 3920 35280
1541 Anusha HV 20000 2000 18000
1542 Sri Sanju P S 24133 2413 21720
1544 Abhirami P R 15000 1500 13500
1545 Anthea Manuual 27900 2790 25110
1547 Hema R 18667 1867 16800
1548 Hridya Sudheer 25000 2500 22500
1550 Nivedita Sri 23333 2333 21000
1552 Tania Felix 10833 1083 9750
1556 Nandana Rakesh 24000 2400 21600
1559 P. S. Arathi 19333 1933 17400
1563 Fathimath Rafna 19333 1933 17400
1564 Mapratha. R 17400 1740 15660
1565 Meenakshy S 24000 2400 21600
1567 Kezia Susan Benison 23000 2300 20700
1568 Saalini P Chandran 25000 2500 22500
1569 Namitha. P 23000 2300 20700
1570 Nehal Bauskar 18667 1867 16800
1571 Sneha raj m.v 23000 2300 20700
1575 Sree Aburva R 26000 2600 23400
1576 Anagha K 20700 2070 18630
1578 Rashi Sharma 20000 2000 18000
1579 Gayathri v Binu 24167 2417 21750
1581 Noufeera.k 25000 2500 22500
1582 Marissa Ruth Furtado 25000 2500 22500
1584 S P Shalini 24000 2400 21600
1585 Kriti Basu 29400 2940 26460
1586 Eloa Gladis 19333 1933 17400
1588 Aishwarya Murthy 25000 2500 22500
1592 Prarthana Mazumdar 17325 1733 15593
1593 Pratheeksha Satheesh 24167 2417 21750
1596 Amrutha C 19333 1933 17400
1597 Kanikha k 25000 2500 22500
1598 Amitha Joseph 21000 2100 18900
1599 Adale Chewang 23000 2300 20700
1603 Misbah Fasihuddin 24000 2400 21600
1604 Niroosha chandra 25000 2500 22500
1605 Ruchitha A 20000 2000 18000
1606 Suprabha GM 23000 2300 20700
1607 Sradha Menon 30000 3000 27000
1608 Bhoomika M 25000 2500 22500
1609 Trisha P 24000 2400 21600
1610 Rakshata Balachandra Salgundi 23000 2300 20700
1612 Safia PS 24000 2400 21600
1613 Divya Nayana Ratakonda 24167 2417 21750
1614 Neimenuo Chadi 24000 2400 21600
1615 Nazia Fathima S 24167 2417 21750
1616 P. Srinithi 23000 2300 20700
1617 Rani Gopal Ganjave 25000 2500 22500
1619 Shehina Shan A 22233 2223 20010
1620 Rashi pundhir 24000 2400 21600
1621 Varshini Selvakumar 21250 2125 19125
1622 Princy immaculate 18000 1800 16200
1623 Nishitha Oruganti 16433 1643 14790
1624 Sneha latha k 30000 3000 27000
1626 Sneha K P 23000 2300 20700
1627 Meghana R 24167 2417 21750
1628 Meghana R S 20000 2000 18000
1629 K. K. Srividya 26567 2657 23910
1630 Benita Charles 24167 2417 21750
1631 Ngawang Saldon 23000 2300 20700
1632 Kavya P 23000 2300 20700
1633 Simran Jagdal 20700 2070 18630
1634 Sindhu A 24000 2400 21600
1635 Fiza Akbar 23333 2333 21000
1636 Pavani. S 25833 2583 23250
1637 Protikhya Kotoky 23000 2300 20700
1638 Sushmitha Das 25833 2583 23250
1639 Chakshika Kamboj 23000 2300 20700
1642 Diya Sana K N 23000 2300 20700
1643 Hasna Suhaib A 24000 2400 21600
1644 Uma Kedia 21666 2167 19499
1645 Meghna Dharmarajan 17333 1733 15600
1646 Preeti Mondal 14733 1473 13260
1648 Sherlyn Rachel R 19167 1917 17250
1649 Rithanya S 17333 1733 15600
1650 Nauf Arabi 14167 1417 12750
1651 Bareen Zarkoob 19933 1993 17940
1652 CH Vidhatri 13033 1303 11730
1653 Trisha Biswas 14567 1457 13110
1654 Anushka Joshi 12667 1267 11400
1655 Rakhshaan Shamoodah 8433 843 7590
1656 Adiba Kalimi 9200 920 8280
1657 Sumitha P 8000 800 7200
1658 Kirti Tiwari 10833 1083 9750
1660 Chandana S 15000 1500 13500
1664 Aashlin Elizabeth A 11500 1150 10350
1494 Varshika 16666 1667 14999
1364 Shruti gupta 16666 1667 14999
1032 jessima 8333 833 7500
1366 Vaishnavi Ravindran 4167 417 3750
1488 Nivita 3667 367 3300
1659 Priyadharshini 9967 997 8970
1640 Chetana 8666 867 7799
1481 Anuradha Koch 10666 1067 9599
1661 Vinothini 2500 250 2250
1210 Sukanya Tripathy 21926 2193 19733
`;

const rawFeb2025 = `
1006 Anisha Kesarla 43520 4352 33897
1007 Amrapali Guha Majumder 5600 560 4200
1009 Balambal Ganesh 44864 4486 30923
1026 Chithra M 24200 2420 21780
1032 Jessima Pastina 20832 2083 18749
1043 Krupa Mohan 61430 6143 55287
1050 Raajasi Godbole 52610 5261 47349
1053 Reeba Shaji 38100 3810 34290
1061 Shaima Nathalia Dsa 21889 2189 19700
1063 Sirisha SR 56967 5697 51270
1073 Thrisha Senthil 18134 1813 16321
1074 Ume Sabah 27378 2738 21062
1079 Anusha Alva 83202 8321 74883
1082 Nikita Nath 29700 2970 24230
1112 Siri S. Kamath 59350 5935 47255
1123 Divya Dogra 51400 5140 46260
1126 Jayamaikodi S. 33580 3358 26119
1145 Athira Thomas 25000 2500 20000
1160 V Sahana 53825 5383 47603
1167 Aiswarya Rajeev 47646 4765 42881
1172 Faryal Fazal 36932 3693 29954
1180 Vijayashri A. 8400 840 6790
1190 Michel Sandra 41593 4159 33314
1193 Aifha P 43480 4348 39132
1208 Annsweeta James 19000 1900 15200
1210 Sukanya Tripathy 23613 2361 19059
1218 Tanvika Ellore 29620 2962 7448
1229 Brigetta Chakraborty 36200 3620 32580
1235 Ananya Chakroborty 25000 2500 20000
1239 Bhavna Seervi 28600 2860 22700
1251 Mrinalini Das 23333 2333 18583
1257 Pratiti Das 31333 3133 28200
1262 Sarangi Krishna P 32800 3280 27020
1271 Ardra Luke Deedi 25000 2500 19960
1272 Arunashree S 37333 3733 33600
1277 Drisya Rajeev 40027 4003 36024
1278 Haridra Vivek 26400 2640 20783
1279 Jeena Reji 25000 2500 20083
1280 Mahak Rathi 27017 2702 24315
1288 Oindrila Bhattacharya 41500 4150 33340
1307 Ankita Komath 22000 2200 17600
1309 Anupriyadharshi ni Kannan 35880 3588 28572
1310 Arunima S Kumar 30000 3000 23860
1313 Iqra Sadaf S. 27500 2750 22250
1318 Safaniya A 19933 1993 15793
1321 Tintu James 26000 2600 20800
1323 Bruno Vansio Mansio 23967 2397 21570
1325 Gayatri J 22050 2205 19658
1329 Sanika Anoop K. 29458 2946 23651
1331 Sandra Raj 34400 3440 27380
1337 Binsha 40100 4010 32650
1339 Mariyam Shadin 42800 4280 34240
1344 Rachel George 23393 2339 18634
1346 Santra Jacob 34720 3472 28300
1348 Varsha H. 40700 4070 32680
1353 Anaswara PS 23100 2310 18087
1356 Divya G. 26400 2640 21260
1360 Madhu Shalini R S 30253 3025 23218
1364 Shruti Gupta 25000 2500 20000
1366 Vaishnavi Ravindran 30400 3040 27360
1369 Ekta Joshi 15333 1533 11800
1371 Eesha Borthakur 34600 3460 31140
1378 Spoorthi P 26200 2620 21223
1385 Anagha A. 25000 2500 20000
1386 Ayushi Pandey 22233 2223 17760
1392 Shravani P 35000 3500 31500
1394 Swetha Raj P.P 23000 2300 18400
1397 Sneha P S 26200 2620 23580
1401 Nitya Chaitanya 21267 2127 16940
1405 Hrithika Krishna 35500 3550 28470
1409 Athullya Philip 22000 2200 17600
1418 Neha Mariya 20700 2070 16430
1420 Akila Reddy 23000 2300 18400
1421 Abirami Siddheshwar Kharatmal 18667 1867 16800
1425 Ananya Sreedhar 29600 2960 23620
1427 Hannah Jacob 28160 2816 22228
1428 Sataparni 25000 2500 20000
1429 Manasvi Tyagi 34400 3440 27718
1432 Rishu Singh 18000 1800 14400
1433 Priyadarshini 19333 1933 15450
1437 Sudeepti Pillai 27167 2717 24450
1439 Varna Unni 28400 2840 23260
1441 Badhriya M 25000 2500 20000
1443 Ardra Saju 25400 2540 20320
1444 Anagha Regi 27000 2700 21600
1448 Deepali Pradeep 8333 833 5375
1449 Jeneepeaceful Iawphniaw 24800 2480 20020
1451 Namratha N 29200 2920 23780
1454 Priscilla 31933 3193 26214
1455 Priyanka MK 23000 2300 20700
1456 Rasika 25000 2500 20000
1457 Sneha Yohanan 23000 2300 18400
1458 Sona Saji 22233 2223 17710
1459 Vaishnavi Patra 18000 1800 14460
1460 Visnupriya 23000 2300 18400
1465 Prachi Patel 25000 2500 20000
1467 Pratiti Das 31400 3140 24560
1471 Aleena Shiby 22233 2223 17863
1472 Misiriya K 23000 2300 18477
1473 Sriparna Paul 29667 2967 26700
1475 Shravya S 23000 2300 17680
1477 Aparna Choudhary 20700 2070 16330
1479 Ananya Sharma 23000 2300 18477
1480 Anaswara Maria Paul 23000 2300 18400
1481 Anuradha Koch 20000 2000 16000
1482 Dhvani Manchanda 27983 2798 23035
1483 Dinky Tejwani 30000 3000 24000
1484 Kalpana G 20000 2000 16000
1486 Linette John 23000 2300 18400
1487 Nehal Mathur 25000 2500 22500
1488 Nivita Jain 11333 1133 8200
1489 Oindrila Dutta 37000 3700 29600
1492 Riya Thomas 23000 2300 18400
1494 Varshika 17000 1700 12883
1495 Janhavi M 25000 2500 20000
1496 Vaishnavi M Mulgund 26600 2660 23940
1497 Muskaan Jain 20000 2000 18000
1498 Rinedha Raman 20000 2000 18000
1499 Sonakshi Datta 23333 2333 18633
1502 Komal Munesh 26000 2600 23400
1508 Hansika Anand 43200 4320 36580
1509 Nikhat Sherief 17666 1767 14244
1512 Gowri Nandana 23000 2300 18400
1514 Sunidhi S G 26800 2680 21703
1516 Barasha Nasim 15000 1500 13500
1517 Deva Dharshini 28600 2860 25740
1518 Pooja Prabakaran 29200 2920 26280
1519 Akshaya R 25000 2500 20000
1520 Nikita Badgujar 41200 4120 33320
1522 Manal Razak 23000 2300 20700
1523 Zeba Ahmad 18667 1867 14800
1526 Ann Mary John 19333 1933 15400
1527 Luann 21467 2147 17020
1534 Ann Maria Jose 20000 2000 16000
1535 Jenifer K 20000 2000 16000
1537 Renita Jhonson 15000 1500 13500
1538 Balkirat Kaur 29600 2960 23937
1539 Sandhra Maria Johnson 25000 2500 20000
1540 Sannidhi Nayak 34953 3495 28047
1541 Anusha HV 20000 2000 18000
1542 Sri Sanju P S 23600 2360 21240
1544 Abhirami P R 15000 1500 12050
1545 Anthea Manuual 31000 3100 25220
1547 Hema R 20000 2000 16000
1548 Hridya Sudheer 25000 2500 20000
1550 Nivedita Sri 21667 2167 17250
1552 Tania Felix 19333 1933 15400
1556 Nandana Rakesh 24000 2400 19200
1559 P. S. Arathi 20000 2000 15750
1563 Fathimath Rafna 19333 1933 15400
1564 Mapratha R 18000 1800 16200
1565 Meenakshy S 22400 2240 17840
1567 Kezia Susan Benison 23000 2300 18477
1568 Saalini P Chandran 25000 2500 20000
1569 Namitha P 23000 2300 18400
1570 Nehal Bauskar 18000 1800 16200
1571 Sneha Raj M V 23000 2300 18400
1572 Panchami Nanjundaiah 19167 1917 17250
1575 Sree Aburva R 25400 2540 20380
1576 Anagha K 23000 2300 18220
1579 Gayathri V Binu 25000 2500 20000
1581 Noufeera K 25000 2500 20567
1582 Marissa Ruth Furtado 25000 2500 20000
1584 S P Shalini 23200 2320 18640
1585 Kriti Basu 24000 2400 19200
1586 Eloa Gladis 20000 2000 16050
1587 Deeksha Raj 6667 667 6000
1588 Aishwarya Murthy 20000 2000 16000
1592 Prarthana Mazumdar 23000 2300 18527
1593 Pratheeksha Satheesh 25000 2500 20083
1596 Amrutha C 18667 1867 14800
1597 Kanikha K 25000 2500 22500
1598 Amitha Joseph 21000 2100 16800
1599 Adale Chewang 23000 2300 18400
1603 Misbah Fasihuddin 24000 2400 18720
1604 Niroosha Chandra 25000 2500 20000
1605 Ruchitha A 20000 2000 18000
1606 Suprabha GM 23000 2300 18400
1607 Sradha Menon 30000 3000 24100
1608 Bhoomika M 22500 2250 17750
1609 Trisha P 24000 2400 19200
1610 Rakshata Balachandra Salgundi 23000 2300 18400
1612 Safia PS 24000 2400 19200
1613 Divya Nayana Ratakonda 25000 2500 20000
1614 Neimenuo Chadi 24000 2400 19200
1615 Nazia Fathima S 25000 2500 20000
1616 P Srinithi 22233 2223 17760
1617 Rani Gopal Ganjave 25000 2500 22500
1619 Shehina Shan A 23000 2300 20700
1620 Rashi Pundhir 21600 2160 19440
1621 Varshini Selvakumar 25000 2500 22500
1622 Princy Immaculate 18000 1800 16200
1623 Nishitha Oruganti 20000 2000 18000
1624 Sneha Latha K 30000 3000 27000
1626 Sneha K P 23000 2300 20700
1627 Meghana R 25000 2500 22500
1628 Meghana R S 20000 2000 18000
1629 K K Srividya 25000 2500 22500
1630 Benita Charles 23333 2333 21000
1631 Ngawang Saldon 23000 2300 20700
1632 Kavya P 22233 2223 17787
1633 Simran Jagdal 23000 2300 20700
1634 Sindhu A 24000 2400 21600
1635 Fiza Akbar 24167 2417 21750
1636 Pavani S 25000 2500 22500
1637 Protikhya Kotoky 23000 2300 20700
1638 Sushmitha Das 25000 2500 22500
1639 Chakshika Kamboj 23000 2300 20700
1642 Diya Sana K N 23000 2300 20700
1643 Hasna Suhaib A 11200 1120 10080
1599 Adale 15000 1500 13500
1600 Arvin 21000 2100 18900
1085 Bindiya Shajith 50000 5000 45000
1370 Delta Vargese 13333 1333 12000
1546 Devika 25000 2500 22500
1017 Epahi 33333 3333 30000
1118 Harshada Sukale 40000 4000 36000
1322 Janani Krishnakumar 43500 0 43500
1412 Krishnapriya 40000 4000 36000
1602 Lakshmi 30000 3000 27000
1280 Mahak 15000 1500 13500
1081 Meghana Ravikumar 43500 0 43500
1084 Navya 58000 0 58000
1408 Nicky 100000 2000 98000
1082 Nikita Nath 50000 0 50000
1647 Noori 20000 2000 18000
1389 Pooja 30000 3000 27000
1381 Poornima Rao 21600 2160 19440
1221 Pragya Dwivedi 45000 0 45000
1551 Rohitt 15000 1500 13500
1601 Sagar 16000 1600 14400
1421 Sanjana 11500 1150 10350
1406 Sanjivani 30000 3000 27000
1061 Shaima 40000 4000 36000
1358 Shilpa Noble 48333 4833 43500
1048 Praneesha 5000 500 4500
`;

const parseRawData = (raw: string, month: string, year: number) => {
  const records: PayslipRecord[] = [];
  const lines = raw.trim().split('\n');

  lines.forEach(line => {
    // Basic regex to capture ID, Name (greedy), Gross, TDS, Net
    // Assumes the last 3 chunks are numbers.
    // Regex explanation:
    // ^(\w+)      -> Start with ID (alphanumeric)
    // \s+         -> whitespace
    // (.+?)       -> Name (non-greedy)
    // \s+         -> whitespace
    // ([\d\.]+)   -> Gross
    // \s+         -> whitespace
    // ([\d\.]+)   -> TDS
    // \s+         -> whitespace
    // ([\d\.]+)   -> Net
    // \s*(paid)?$ -> Optional 'paid' text at end
    const match = line.match(/^(\w+)\s+(.+?)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s*(paid)?$/i);

    if (match) {
      const [, id, name, grossStr, tdsStr, netStr] = match;
      records.push({
        id: `${id}-${month}-${year}`,
        employeeId: id,
        month,
        year,
        grossPay: parseFloat(grossStr),
        tds: parseFloat(tdsStr),
        netPay: parseFloat(netStr),
        // Assuming base and allowance are not provided in this simplified format
        // We will handle display logic to show consolidated if 0
        baseSalary: 0,
        allowance: 0,
        reference: 'Paid'
      });
      
      // Update global employee list if not exists
      if (!allEmployees.some(e => e.employeeId === id)) {
        allEmployees.push({
            employeeId: id,
            name: name.trim(),
            email: `${name.trim().toLowerCase().replace(/\s+/g, '.')}@example.com` // Placeholder
        });
      }
    }
  });
  return records;
};

// Initialize Data
const allEmployees: Employee[] = [...existingEmployees];
const payslipsDec = parseRawData(rawDec2024, 'December', 2025);
const payslipsJan = parseRawData(rawJan2025, 'January', 2026);
const payslipsFeb = parseRawData(rawFeb2025, 'February', 2026);

export const employees = allEmployees.sort((a, b) => a.name.localeCompare(b.name));
export const payslipRecords = [...payslipsDec, ...payslipsJan, ...payslipsFeb];

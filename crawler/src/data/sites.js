/**
 * sites.json — 南京大学站点清单
 *
 * 包含南大所有官方部门与学院的 URL。
 * 由 https://www.nju.edu.cn/xybm.htm 提取。
 */

module.exports = {
  meta: {
    source: 'https://njunju.nju.edu.cn/yxbm2/list.htm',
    generatedAt: new Date().toISOString(),
    note: '由爬虫自动提取，参考 https://njunju.nju.edu.cn/yxbm2/list.htm'
  },

  // ============================================================
  // 学校概况
  // ============================================================
  overview: {
    name: '南大概况',
    sites: [
      { name: '南大简介', url: 'https://www.nju.edu.cn/ndgk/ndjj.htm' },
      { name: '现任领导', url: 'https://www.nju.edu.cn/ndgk/xrld.htm' },
      { name: '历任领导', url: 'https://www.nju.edu.cn/ndgk/lrld.htm' },
      { name: '南大校史', url: 'https://dawww.nju.edu.cn/xswh/ndxs.htm' },
      { name: '南大标识', url: 'https://www.nju.edu.cn/ndgk/ndbs.htm' },
    ]
  },

  // ============================================================
  // 管理部门
  // ============================================================
  admin: {
    name: '党群组织',
    sites: [
      { name: '党委办公室', url: 'https://dwbgs.nju.edu.cn/' },
      { name: '保密办公室（纪委办公室）', url: 'https://jwb.nju.edu.cn/main.htm' },
      { name: '党委巡视工作办公室', url: 'https://xsb.nju.edu.cn/' },
      { name: '党委组织部 党校', url: 'https://zzb.nju.edu.cn/main.htm' },
      { name: '党委宣传部（新闻中心）', url: 'https://xcb.nju.edu.cn/' },
      { name: '校报编辑部', url: 'https://xcb.nju.edu.cn/xbbjb/main.htm' },
      { name: '党委统战部', url: 'https://tzb.nju.edu.cn/main.htm' },
      { name: '党委教师工作部', url: 'https://hr.nju.edu.cn/main.htm' },
      { name: '党委学生工作部', url: 'https://xgb.nju.edu.cn/' },
      { name: '党委人民武装部', url: 'https://xgb.nju.edu.cn/rwzb/list.htm' },
      { name: '党委保卫部', url: 'https://bwc.nju.edu.cn/' },
      { name: '离退休工作处', url: 'https://ltx.nju.edu.cn/' },
      { name: '机关党委', url: 'https://jgdw.nju.edu.cn/main.htm' },
      { name: '后勤服务集团党委', url: 'https://hqjt.nju.edu.cn/main.htm' },
      { name: '科技产业党工委', url: 'https://kjcy.nju.edu.cn/' },
      { name: '政产学研平台党工委', url: 'https://zycxypt.nju.edu.cn/' },
    ]
  },

  // ============================================================
  // 行政部门
  // ============================================================
  admin2: {
    name: '行政部门',
    sites: [
      { name: '校长办公室', url: 'https://ndbgs.nju.edu.cn/' },
      { name: '法制办公室', url: 'https://xiaoban.nju.edu.cn/' },
      { name: '鼓楼校区管理办公室', url: 'https://gl.nju.edu.cn/' },
      { name: '苏州校区建设工作领导小组办公室', url: 'https://njusz.nju.edu.cn/szxcjsb/index.htm' },
      { name: '人力资源处', url: 'https://hr.nju.edu.cn/main.htm' },
      { name: '人才培训交流中心', url: 'https://rcjlzx.nju.edu.cn/' },
      { name: '科学技术研究院', url: 'https://scit.nju.edu.cn/main.htm' },
      { name: '社会科学处', url: 'https://skch.nju.edu.cn/' },
      { name: '学科建设与发展规划办公室', url: 'https://xkb.nju.edu.cn/main.htm' },
      { name: '本科生院', url: 'https://jw.nju.edu.cn/main.htm' },
      { name: '本科招生办公室', url: 'https://bkzs.nju.edu.cn/' },
      { name: '研究生院', url: 'https://grawww.nju.edu.cn/main.htm' },
      { name: '学生就业指导中心', url: 'https://job.nju.edu.cn/' },
      { name: '创新创业与成果转化工作办公室', url: 'https://cxcy.nju.edu.cn/' },
      { name: '技术转移中心', url: 'https://ttc.nju.edu.cn/' },
      { name: '终身教育学院', url: 'https://slle.nju.edu.cn/' },
      { name: '国际合作与交流处（台港澳事务办公室）', url: 'https://wb.nju.edu.cn/main.htm' },
      { name: '招标办公室', url: 'https://zb.nju.edu.cn/' },
      { name: '资产管理处', url: 'https://zcc.nju.edu.cn/' },
      { name: '实验室与设备管理处', url: 'https://sbc.nju.edu.cn/' },
      { name: '基本建设处', url: 'https://jjc.nju.edu.cn/main.htm' },
      { name: '校友事务与发展工作处', url: 'https://alumni.nju.edu.cn/main.htm' },
      { name: '教育发展基金会', url: 'https://njuedf.nju.edu.cn/main.htm' },
      { name: '后勤服务集团', url: 'https://hqjt.nju.edu.cn/main.htm' },
      { name: '浦口校区管理办公室', url: 'https://pkgwh.nju.edu.cn/main.htm' },
      { name: '苏州研究生院', url: 'https://njusz.nju.edu.cn/' },
    ]
  },

  // ============================================================
  // 教学科研单位
  // ============================================================
  academic: {
    name: '教学科研单位',
    sites: [
      { name: '新生学院', url: 'https://xsxy.nju.edu.cn/' },
      { name: '文学院', url: 'http://chin.nju.edu.cn/' },
      { name: '历史学院', url: 'http://history.nju.edu.cn/' },
      { name: '哲学学院', url: 'http://philo.nju.edu.cn/' },
      { name: '新闻传播学院', url: 'http://jc.nju.edu.cn/' },
      { name: '法学院', url: 'https://law.nju.edu.cn/' },
      { name: '商学院', url: 'https://nubs.nju.edu.cn/' },
      { name: '经济学院', url: 'http://njubs.nju.edu.cn/intro.php/a' },
      { name: '管理学院', url: 'http://njubs.nju.edu.cn/intro.php/e' },
      { name: '外国语学院', url: 'http://sfs.nju.edu.cn/' },
      { name: '政府管理学院', url: 'http://public.nju.edu.cn/' },
      { name: '国际关系学院', url: 'https://sis.nju.edu.cn/' },
      { name: '信息管理学院', url: 'http://im.nju.edu.cn/' },
      { name: '社会学院', url: 'http://sociology.nju.edu.cn/' },
      { name: '数学学院', url: 'http://math.nju.edu.cn/' },
      { name: '物理学院', url: 'http://physics.nju.edu.cn/' },
      { name: '天文与空间科学学院', url: 'http://astronomy.nju.edu.cn/' },
      { name: '化学化工学院', url: 'https://chem.nju.edu.cn/' },
      { name: '计算机学院', url: 'http://cs.nju.edu.cn/' },
      { name: '软件学院', url: 'http://software.nju.edu.cn/' },
      { name: '人工智能学院', url: 'http://ai.nju.edu.cn/' },
      { name: '电子科学与工程学院', url: 'http://ese.nju.edu.cn/' },
      { name: '现代工程与应用科学学院', url: 'http://eng.nju.edu.cn/' },
      { name: '环境学院', url: 'http://hjxy.nju.edu.cn/' },
      { name: '地球科学与工程学院', url: 'http://es.nju.edu.cn/' },
      { name: '地理与海洋科学学院', url: 'http://sgos.nju.edu.cn/' },
      { name: '大气科学学院', url: 'http://as.nju.edu.cn/' },
      { name: '南京赫尔辛基大气与地球系统科学学院（南赫学院）', url: 'http://nh.nju.edu.cn/' },
      { name: '生命科学学院', url: 'http://life.nju.edu.cn/' },
      { name: '医学院', url: 'http://med.nju.edu.cn/' },
      { name: '工程管理学院', url: 'http://sme.nju.edu.cn/' },
      { name: '匡亚明学院', url: 'http://dii.nju.edu.cn/' },
      { name: '海外教育学院', url: 'http://hwxy.nju.edu.cn/' },
      { name: '建筑与城市规划学院', url: 'http://arch.nju.edu.cn/' },
      { name: '马克思主义学院', url: 'http://marxism.nju.edu.cn/' },
      { name: '艺术学院', url: 'https://art.nju.edu.cn/' },
      { name: '金陵学院（独立学院）', url: 'https://jlxy.nju.edu.cn/' },
      { name: '智能科学与技术学院', url: 'https://is.nju.edu.cn/main.htm' },
      { name: '智能软件与工程学院', url: 'https://ise.nju.edu.cn/' },
      { name: '集成电路学院', url: 'https://ic.nju.edu.cn/main.htm' },
      { name: '数字经济与管理学院', url: 'https://sdem.nju.edu.cn/main.htm' },
      { name: '能源与资源学院', url: 'https://sser.nju.edu.cn/' },
      { name: '国家卓越工程师学院', url: 'https://gcee.nju.edu.cn/' },
      { name: '机器人与自动化学院', url: 'https://ra.nju.edu.cn/' },
      { name: '未来技术学院', url: 'https://futuretech.nju.edu.cn/' },
      { name: '前沿科学学院', url: 'https://frontier.nju.edu.cn/main.htm' },
      { name: '生物医学工程学院', url: 'https://bme.nju.edu.cn/' },
      { name: '教育研究院·陶行知教师教育学院', url: 'http://edu.nju.edu.cn/' },
      { name: '大学外语部', url: 'http://dafls.nju.edu.cn/' },
      { name: '体育部', url: 'http://tyb.nju.edu.cn/' },
      { name: '中美文化研究中心', url: 'https://hnc.nju.edu.cn/' },
      { name: '中国思想家研究中心', url: 'http://sxsyj.nju.edu.cn/' },
      { name: '国际地球系统科学研究所', url: 'https://essi.nju.edu.cn/main.htm' },
      { name: '人文社会科学高级研究院', url: 'https://ias.nju.edu.cn/' },
      { name: '现代生物研究院', url: 'https://imb.nju.edu.cn/' },
      { name: '长江产业发展研究院', url: 'https://iddi.nju.edu.cn/' },
    ]
  },

  // ============================================================
  // 医学院（附属医院见下方）
  // ============================================================
  medical: {
    name: '医学院',
    sites: [
      { name: '医学院', url: 'https://med.nju.edu.cn/' },
      { name: '附属鼓楼医院', url: 'https://med.nju.edu.cn/附属鼓楼医院/main.htm' },
      { name: '附属金陵医院（东部战区总医院）', url: 'https://med.nju.edu.cn/附属金陵医院/main.htm' },
      { name: '附属口腔医院', url: 'https://med.nju.edu.cn/附属口腔医院/main.htm' },
      { name: '附属泰康仙林鼓楼医院', url: 'https://med.nju.edu.cn/附属泰康仙林鼓楼医院/main.htm' },
      { name: '附属盐城第一医院', url: 'https://med.nju.edu.cn/附属盐城第一医院/main.htm' },
      { name: '附属苏州医院', url: 'https://med.nju.edu.cn/附属苏州医院/main.htm' },
    ]
  },

  // ============================================================
  // 公共服务单位
  // ============================================================
  service: {
    name: '公共服务单位',
    sites: [
      { name: '图书馆', url: 'https://lib.nju.edu.cn/' },
      { name: '信息化建设管理服务中心', url: 'https://itsc.nju.edu.cn/' },
      { name: '档案馆 校史馆', url: 'https://dawww.nju.edu.cn/' },
      { name: '博物馆', url: 'https://museum.nju.edu.cn/' },
      { name: '出版社', url: 'https://www.njupco.com/' },
      { name: '学报编辑部', url: 'https://jnju.nju.edu.cn/' },
      { name: '教育技术中心', url: 'https://etc.nju.edu.cn/' },
      { name: '现代分析中心', url: 'https://afc.nju.edu.cn/' },
      { name: '校医院', url: 'https://hospital.nju.edu.cn/' },
      { name: '心理健康教育与研究中心', url: 'https://njuxlzx.nju.edu.cn/main.htm' },
      { name: '科研设施共享中心', url: 'https://cssrf.nju.edu.cn/' },
      { name: '超算中心', url: 'https://hpcc.nju.edu.cn/main.htm' },
      { name: '教师教学发展中心', url: 'https://ctl.nju.edu.cn/main.htm' },
      { name: '资本运营有限公司', url: 'https://zbyy.nju.edu.cn/' },
      { name: '中国社会科学研究评价中心', url: 'https://cssr.nju.edu.cn/' },
    ]
  },

  // ============================================================
  // 专题网站
  // ============================================================
  special: {
    name: '专题网站',
    sites: [
      { name: '信息公开', url: 'https://xxgk.nju.edu.cn/main.htm' },
      { name: '人才招聘', url: 'https://rczp.nju.edu.cn/' },
      { name: '本科招生', url: 'https://bkzs.nju.edu.cn/' },
      { name: '研究生招生', url: 'https://yzb.nju.edu.cn/main.htm' },
    ]
  },

  // ============================================================
  // 搜索相关（单独处理）
  // ============================================================
  search: {
    name: '搜索门户',
    sites: [
      { name: '南京大学智搜门户', url: 'https://search.nju.edu.cn/' },
    ]
  }
};

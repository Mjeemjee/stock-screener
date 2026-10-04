/** 数据源解析器：为本机全天候部署预留的取数抽象。
 *
 * 默认行为与现状一致：相对路径 ./data（GitHub Pages 或本机静态服务同构，
 * 数据随站点一起部署，无任何配置）。
 *
 * 当站点需要读取「另一台全天候机器」上的新鲜数据（Futu OpenD 常驻刷新）时，
 * 用 URL 查询参数指定数据源，选择会持久化到 localStorage：
 *   ?data=http://192.168.1.10:8080/data   → 改从该地址取数
 *   ?data=local                           → 恢复默认（随站点部署的数据）
 *
 * 全天候本机的标准拓扑（详见「指南」页）：
 *   Futu OpenD 常驻 → refresh_data.py 定时刷新 → 本机静态服务（数据目录）
 *   → 手机/其他设备经局域网访问站点，再以 ?data= 指向该数据目录。
 */

const STORAGE_KEY = 'pb.dataBase'
const DEFAULT_BASE = './data'

function normalize(base: string): string {
  return base.replace(/\/+$/, '')
}

function readQueryOverride(): string | null {
  try {
    const v = new URLSearchParams(window.location.search).get('data')
    return v && v.trim() ? v.trim() : null
  } catch {
    return null
  }
}

// 模块加载时应用一次查询参数覆盖（写入/清除持久化）
const override = readQueryOverride()
if (override) {
  try {
    if (override === 'local') window.localStorage.removeItem(STORAGE_KEY)
    else window.localStorage.setItem(STORAGE_KEY, normalize(override))
  } catch {
    /* localStorage 不可用时静默降级为默认数据源 */
  }
}

export function currentDataBase(): string {
  try {
    return window.localStorage.getItem(STORAGE_KEY) ?? DEFAULT_BASE
  } catch {
    return DEFAULT_BASE
  }
}

/** 由数据相对路径（如 'history/us.json'）得到完整取数地址 */
export function dataUrl(rel: string): string {
  return `${currentDataBase()}/${rel.replace(/^\/+/, '')}`
}

/** 是否正在使用外部数据源（非随站部署） */
export function usingExternalData(): boolean {
  return currentDataBase() !== DEFAULT_BASE
}

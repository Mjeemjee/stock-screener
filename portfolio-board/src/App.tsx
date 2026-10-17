import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router'
import Screener from './pages/Screener'

const Holdings = lazy(() => import('./pages/Holdings'))
const Guide = lazy(() => import('./pages/Guide'))
const Backtest = lazy(() => import('./pages/Backtest'))
const Learn = lazy(() => import('./pages/Learn'))
const Tracking = lazy(() => import('./pages/Tracking'))
const StockDetail = lazy(() => import('./pages/StockDetail'))
const Watchlist = lazy(() => import('./pages/Watchlist'))
const InvestmentMethods = lazy(() => import('./pages/InvestmentMethods'))

export default function App() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-muted-foreground" role="status">正在加载页面...</div>}>
      <Routes>
      <Route path="/" element={<Screener />} />
      <Route path="/backtest" element={<Backtest />} />
      <Route path="/methods" element={<InvestmentMethods />} />
      <Route path="/methods/:id" element={<InvestmentMethods />} />
      <Route path="/learn" element={<Learn />} />
      <Route path="/holdings" element={<Holdings />} />
      <Route path="/guide" element={<Guide />} />
      <Route path="/tracking" element={<Tracking />} />
      <Route path="/stock/:code" element={<StockDetail />} />
      <Route path="/watchlist" element={<Watchlist />} />
      </Routes>
    </Suspense>
  )
}

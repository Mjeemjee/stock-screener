import { Routes, Route } from 'react-router'
import Screener from './pages/Screener'
import Holdings from './pages/Holdings'
import Guide from './pages/Guide'
import Backtest from './pages/Backtest'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Screener />} />
      <Route path="/backtest" element={<Backtest />} />
      <Route path="/holdings" element={<Holdings />} />
      <Route path="/guide" element={<Guide />} />
    </Routes>
  )
}

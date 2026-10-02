import { Routes, Route } from 'react-router'
import Screener from './pages/Screener'
import Holdings from './pages/Holdings'
import Guide from './pages/Guide'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Screener />} />
      <Route path="/holdings" element={<Holdings />} />
      <Route path="/guide" element={<Guide />} />
    </Routes>
  )
}

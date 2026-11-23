
import { useEffect, useState } from 'react'
import './App.css'

const TENANT_ID = '1bb3a9f9-1b23-4f0a-8583-bf32a89490b9'

interface Product {
  id: string
  sku_code: string
  product_name: string
  brand?: string | null
  category?: string | null
  is_active: boolean
}

interface InventoryItem {
  id: string
  location_id: string
  product_id: string
  on_hand: string
  reserved: string
  inbound: string
  available: string
}

interface ProductPage {
  items: Product[]
  total: number
}

interface InventoryPage {
  items: InventoryItem[]
  total: number
}

interface PredictionResult {
  stockout_probability: number
  risk_level: 'low' | 'medium' | 'high'
  prediction_horizon_days: number
  prediction_date: string
  model_version: string
  data_source: string
  is_production_ready: boolean
}


interface SupplierRecommendation {
  location_id: string
  product_id: string
  supplier_id: string
  supplier_product_id: string
  forecast_demand: string
  safety_stock: string
  available_inventory: string
  confirmed_inbound: string
  required_quantity: string
  requires_replenishment: boolean
  recommended_quantity: string
  supplier_name: string
  supplier_code: string
  supplier_sku: string | null
  unit_cost: string
  currency: string
  estimated_total_cost: string
  lead_time_days: number
  minimum_order_quantity: string
  pack_size: string
  is_preferred_supplier: boolean
}


interface PurchaseOrderLine {
  id: string
  supplier_sku: string | null
  ordered_quantity: string
  received_quantity: string
}

interface PurchaseOrder {
  id: string
  po_number: string
  status: string
  currency: string
  total_amount: string
  external_reference: string | null
  created_at: string
  lines: PurchaseOrderLine[]
}

interface PurchaseOrderPage {
  items: PurchaseOrder[]
  total: number
}

function App() {
  const [products, setProducts] = useState<Product[]>([])
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [prediction, setPrediction] = useState<PredictionResult | null>(null)
  const [predicting, setPredicting] = useState(false)
  const [predictionError, setPredictionError] = useState('')

  const [predictionDate, setPredictionDate] = useState('2026-11-23')
  const [salesLag1, setSalesLag1] = useState('2')
  const [salesLag7, setSalesLag7] = useState('0')
  const [sales7d, setSales7d] = useState('14')
  const [sales14d, setSales14d] = useState('14')
  const [sales28d, setSales28d] = useState('14')
  const [avgDailySales, setAvgDailySales] = useState('2')
  const [availableStock, setAvailableStock] = useState('103')
  const [supplierRecommendation, setSupplierRecommendation] = useState<SupplierRecommendation | null>(null)
  const [recommending, setRecommending] = useState(false)
  const [replenishmentError, setReplenishmentError] = useState('')
  const [forecastDemand, setForecastDemand] = useState('110')
  const [safetyStock, setSafetyStock] = useState('10')

  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrder[]>([])
  const [poError, setPoError] = useState('')
  const [poMessage, setPoMessage] = useState('')
  const [poBusyId, setPoBusyId] = useState('')
  const [receiveQuantities, setReceiveQuantities] = useState<Record<string, string>>({})

  useEffect(() => {
    async function loadDashboard() {
      try {
        const headers = { 'X-Tenant-ID': TENANT_ID }

        const [productResponse, inventoryResponse] = await Promise.all([
          fetch('/api/v1/products', { headers }),
          fetch('/api/v1/inventory', { headers }),
        ])

        if (!productResponse.ok || !inventoryResponse.ok) {
          throw new Error('Unable to load dashboard data. Check the backend connection.')
        }

        const productData: ProductPage = await productResponse.json()
        const inventoryData: InventoryPage = await inventoryResponse.json()

        setProducts(productData.items ?? [])
        setInventory(inventoryData.items ?? [])

        if (inventoryData.items?.length) {
          setAvailableStock(String(inventoryData.items[0].available))
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Something went wrong.')
      } finally {

        setLoading(false)
      }
    }

    loadDashboard()
  }, [])

  async function loadPurchaseOrders() {
    try {
      const response = await fetch('/api/v1/purchase-orders', {
        headers: { 'X-Tenant-ID': TENANT_ID },
      })
      if (!response.ok) {
        throw new Error(`Could not load purchase orders (${response.status})`)
      }
      const data: PurchaseOrderPage = await response.json()
      setPurchaseOrders(data.items ?? [])
      setPoError('')
    } catch (err) {
      setPoError(err instanceof Error ? err.message : 'Could not load purchase orders.')
    }
  }

  useEffect(() => {
    loadPurchaseOrders()
  }, [])

  const totalOnHand = inventory.reduce(
    (sum, item) => sum + Number(item.on_hand), 0,
  )

  const totalReserved = inventory.reduce(
    (sum, item) => sum + Number(item.reserved), 0,
  )

  const totalAvailable = inventory.reduce(
    (sum, item) => sum + Number(item.available), 0,
  )

  const getProduct = (productId: string) =>
    products.find((product) => product.id === productId)

  async function runPrediction(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const item = inventory[0]

    if (!item) {
      setPredictionError('No inventory record is available for prediction.')
      return
    }

    setPredicting(true)
    setPredictionError('')
    setPrediction(null)

    const date = new Date(`${predictionDate}T00:00:00`)
    const dayOfWeek = (date.getDay() + 6) % 7

    const payload = {
      location_id: item.location_id,
      product_id: item.product_id,
      prediction_date: predictionDate,
      sales_lag_1: Number(salesLag1),
      sales_lag_7: Number(salesLag7),
      sales_7d: Number(sales7d),
      sales_14d: Number(sales14d),
      sales_28d: Number(sales28d),
      avg_daily_sales_7d: Number(avgDailySales),
      available_stock: Number(availableStock),
      day_of_week: dayOfWeek,
    }

    try {
      const response = await fetch('/api/v1/stockout/predict', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': TENANT_ID,
        },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => null)
        throw new Error(
          errorData?.detail
            ? JSON.stringify(errorData.detail)
            : `Prediction request failed (${response.status})`,
        )
      }

      const result: PredictionResult = await response.json()
      setPrediction(result)
    } catch (err) {
      setPredictionError(
        err instanceof Error ? err.message : 'Prediction failed.',
      )
    } finally {

      setPredicting(false)
    }
  }

  async function runSupplierRecommendation(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const item = inventory[0]

    if (!item) {
      setReplenishmentError('No inventory record is available.')
      return
    }

    setRecommending(true)
    setReplenishmentError('')
    setSupplierRecommendation(null)

    try {
      const response = await fetch('/api/v1/replenishment/supplier-recommendation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': TENANT_ID,
        },
        body: JSON.stringify({
          location_id: item.location_id,
          product_id: item.product_id,
          forecast_demand: Number(forecastDemand),
          safety_stock: Number(safetyStock),
        }),
      })

      if (!response.ok) {
        throw new Error(`Supplier recommendation failed (${response.status})`)
      }

      const result: SupplierRecommendation = await response.json()
      setSupplierRecommendation(result)
    } catch (err) {
      setReplenishmentError(
        err instanceof Error ? err.message : 'Supplier recommendation failed.',
      )
    } finally {
      setRecommending(false)
    }
  }

  async function createPurchaseOrder() {
    if (!supplierRecommendation) return

    setPoBusyId('create')
    setPoError('')
    setPoMessage('')

    const uniqueId = Date.now().toString()

    try {
      const response = await fetch('/api/v1/purchase-orders', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': TENANT_ID,
        },
        body: JSON.stringify({
          supplier_id: supplierRecommendation.supplier_id,
          location_id: supplierRecommendation.location_id,
          po_number: `PO-STOCKIQ-${uniqueId}`,
          currency: supplierRecommendation.currency,
          idempotency_key: `stockiq-${uniqueId}`,
          notes: 'Created from StockIQ supplier recommendation.',
          lines: [{
            product_id: supplierRecommendation.product_id,
            supplier_product_id: supplierRecommendation.supplier_product_id,
            ordered_quantity: Number(supplierRecommendation.recommended_quantity),
          }],
        }),
      })

      if (!response.ok) {
        const data = await response.json().catch(() => null)
        throw new Error(data?.detail ? JSON.stringify(data.detail) : `Create PO failed (${response.status})`)
      }

      setPoMessage('Draft purchase order created successfully.')
      await loadPurchaseOrders()
    } catch (err) {
      setPoError(err instanceof Error ? err.message : 'Could not create purchase order.')
    } finally {
      setPoBusyId('')
    }
  }

  async function runPoAction(id: string, action: 'approve' | 'submit') {
    setPoBusyId(id)
    setPoError('')
    setPoMessage('')

    try {
      const response = await fetch(`/api/v1/purchase-orders/${id}/${action}`, {
        method: 'POST',
        headers: { 'X-Tenant-ID': TENANT_ID },
      })

      if (!response.ok) {
        const data = await response.json().catch(() => null)
        throw new Error(data?.detail ? JSON.stringify(data.detail) : `${action} failed (${response.status})`)
      }

      setPoMessage(action === 'approve'
        ? 'Purchase order approved.'
        : 'Purchase order submitted to the mock ERP.')
      await loadPurchaseOrders()
    } catch (err) {
      setPoError(err instanceof Error ? err.message : `Could not ${action} purchase order.`)
    } finally {
      setPoBusyId('')
    }
  }

  async function receiveGoods(poId: string, lineId: string, quantity: string) {
    const amount = Number(quantity)
    if (!Number.isFinite(amount) || amount <= 0) {
      setPoError('Enter a valid receiving quantity greater than zero.')
      return
    }

    setPoBusyId(poId)
    setPoError('')
    setPoMessage('')

    try {
      const response = await fetch(`/api/v1/purchase-orders/${poId}/receive`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': TENANT_ID,
        },
        body: JSON.stringify({
          line_id: lineId,
          quantity: amount,
          idempotency_key: `stockiq-receive-${lineId}-${Date.now()}`,
          notes: 'Goods received through StockIQ dashboard.',
        }),
      })

      if (!response.ok) {
        const data = await response.json().catch(() => null)
        throw new Error(data?.detail ? JSON.stringify(data.detail) : `Goods receipt failed (${response.status})`)
      }

      setPoMessage('Goods received successfully. Inventory has been updated.')
      await loadPurchaseOrders()

      const inventoryResponse = await fetch('/api/v1/inventory', {
        headers: { 'X-Tenant-ID': TENANT_ID },
      })
      if (inventoryResponse.ok) {
        const inventoryData: InventoryPage = await inventoryResponse.json()
        setInventory(inventoryData.items ?? [])
        if (inventoryData.items?.length) {
          setAvailableStock(String(inventoryData.items[0].available))
        }
      }
    } catch (err) {
      setPoError(err instanceof Error ? err.message : 'Could not receive goods.')
    } finally {
      setPoBusyId('')
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">IQ</div>
          <div>
            <h2>StockIQ</h2>
            <span>INTELLIGENT COMMERCE</span>
          </div>
        </div>

        <p className="nav-label">WORKSPACE</p>
        <nav>
          <a className="active" href="#dashboard">▦ Dashboard</a>
          <a href="#inventory">▤ Inventory</a>
          <a href="#predictions">◉ Stockout Predictions</a>
          <a href="#replenishment">↗ Replenishment</a>
          <a href="#purchase-orders">▣ Purchase Orders</a>
        </nav>

        <div className="sidebar-bottom">
          <div className="status-dot" />
          {error ? 'Backend connection issue' : 'Backend connected'}
          <small>IDEA-1026 · Demo environment</small>
        </div>
      </aside>

      <main className="main-content" id="dashboard">
        <header className="topbar">
          <div>
            <p className="eyebrow">OVERVIEW / DASHBOARD</p>
            <h1>Inventory Overview</h1>
            <p className="subtitle">
              Monitor stock health and replenishment activity.
            </p>
          </div>
          <div className="demo-tag">LIVE API DATA</div>
        </header>

        {loading ? (
          <div className="panel">Loading dashboard data...</div>
        ) : error ? (
          <div className="error-message">{error}</div>
        ) : (
          <>
            <section className="welcome-banner">
              <div>
                <p className="eyebrow">STOCK INTELLIGENCE</p>
                <h2>Welcome to StockIQ</h2>
                <p>
                  Your inventory dashboard is connected to the IDEA-1026 backend.
                </p>
              </div>
              <div className="banner-icon">✦</div>
            </section>

            <section className="stats-grid">
              <div className="stat-card">
                <span className="stat-label">Active Products</span>
                <h2>{products.filter((p) => p.is_active).length}</h2>
                <p>Products in catalogue</p>
              </div>

              <div className="stat-card">
                <span className="stat-label">Tracked Inventory</span>
                <h2>{inventory.length}</h2>
                <p>Inventory records</p>
              </div>

              <div className="stat-card">
                <span className="stat-label">Available Units</span>
                <h2>{totalAvailable.toLocaleString()}</h2>
                <p>Ready for sale</p>
              </div>

              <div className="stat-card">
                <span className="stat-label">Reserved Units</span>
                <h2>{totalReserved.toLocaleString()}</h2>
                <p>Allocated stock</p>
              </div>
            </section>

            <section className="content-grid">
              <div className="panel" id="inventory">
                <div className="panel-heading">
                  <div>
                    <h3>Inventory Summary</h3>
                    <p>Current stock levels from PostgreSQL</p>
                  </div>
                  <span className="live-label">● LIVE</span>
                </div>

                <div className="inventory-summary">
                  <div>
                    <span>Total on hand</span>
                    <strong>{totalOnHand.toLocaleString()}</strong>
                  </div>
                  <div>
                    <span>Total available</span>
                    <strong>{totalAvailable.toLocaleString()}</strong>
                  </div>
                  <div>
                    <span>Total reserved</span>
                    <strong>{totalReserved.toLocaleString()}</strong>
                  </div>
                </div>

                <div className="table-wrap">
                  <table className="inventory-table">
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th>SKU</th>
                        <th>On hand</th>
                        <th>Reserved</th>
                        <th>Inbound</th>
                        <th>Available</th>
                      </tr>
                    </thead>
                    <tbody>
                      {inventory.map((item) => {
                        const product = getProduct(item.product_id)

                        return (
                          <tr key={item.id}>
                            <td>
                              <strong>
                                {product?.product_name ?? 'Unknown product'}
                              </strong>
                            </td>
                            <td>{product?.sku_code ?? '—'}</td>
                            <td>{Number(item.on_hand).toLocaleString()}</td>
                            <td>{Number(item.reserved).toLocaleString()}</td>
                            <td>{Number(item.inbound).toLocaleString()}</td>
                            <td className="available-value">
                              {Number(item.available).toLocaleString()}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="panel prediction-panel" id="predictions">
                <div className="panel-heading">
                  <div>
                    <h3>Stockout Predictions</h3>
                    <p>Seven-day stockout risk analysis</p>
                  </div>
                  <span className="live-label">● API READY</span>
                </div>

                <p className="demo-warning">
                  Demo model: trained on synthetic data. Input values below are
                  illustrative and should not be treated as a production forecast.
                </p>

                <div className="selected-product">
                  <span>Selected inventory product</span>
                  <strong>
                    {getProduct(inventory[0]?.product_id ?? '')?.product_name
                      ?? 'No inventory product'}
                  </strong>
                  <small>
                    SKU: {getProduct(inventory[0]?.product_id ?? '')?.sku_code ?? '—'}
                  </small>
                </div>

                <form onSubmit={runPrediction} className="prediction-form">
                  <div className="form-field">
                    <label htmlFor="prediction-date">Prediction date</label>
                    <input
                      id="prediction-date"
                      type="date"
                      value={predictionDate}
                      onChange={(e) => setPredictionDate(e.target.value)}
                      required
                    />
                  </div>

                  <div className="prediction-input-grid">
                    <div className="form-field">
                      <label htmlFor="sales-lag-1">Sales yesterday</label>
                      <input id="sales-lag-1" type="number" min="0" step="any"
                        value={salesLag1} onChange={(e) => setSalesLag1(e.target.value)} required />
                    </div>

                    <div className="form-field">
                      <label htmlFor="sales-lag-7">Sales 7 days ago</label>
                      <input id="sales-lag-7" type="number" min="0" step="any"
                        value={salesLag7} onChange={(e) => setSalesLag7(e.target.value)} required />
                    </div>

                    <div className="form-field">
                      <label htmlFor="sales-7d">Sales last 7 days</label>
                      <input id="sales-7d" type="number" min="0" step="any"
                        value={sales7d} onChange={(e) => setSales7d(e.target.value)} required />
                    </div>

                    <div className="form-field">
                      <label htmlFor="sales-14d">Sales last 14 days</label>
                      <input id="sales-14d" type="number" min="0" step="any"
                        value={sales14d} onChange={(e) => setSales14d(e.target.value)} required />
                    </div>

                    <div className="form-field">
                      <label htmlFor="sales-28d">Sales last 28 days</label>
                      <input id="sales-28d" type="number" min="0" step="any"
                        value={sales28d} onChange={(e) => setSales28d(e.target.value)} required />
                    </div>

                    <div className="form-field">
                      <label htmlFor="avg-sales">Average daily sales (7d)</label>
                      <input id="avg-sales" type="number" min="0" step="any"
                        value={avgDailySales} onChange={(e) => setAvgDailySales(e.target.value)} required />
                    </div>

                    <div className="form-field">
                      <label htmlFor="available-stock">Available stock</label>
                      <input id="available-stock" type="number" min="0" step="any"
                        value={availableStock} onChange={(e) => setAvailableStock(e.target.value)} required />
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="predict-button"
                    disabled={predicting || inventory.length === 0}
                  >
                    {predicting ? 'Calculating prediction...' : 'Predict Stockout Risk'}
                  </button>
                </form>

                {predictionError && (
                  <div className="error-message">{predictionError}</div>
                )}

                {prediction && (
                  <div className="prediction-result">
                    <h3>Prediction Result</h3>
                    <div className={`risk-result risk-${prediction.risk_level}`}>
                      <span>Risk level</span>
                      <strong>{prediction.risk_level.toUpperCase()}</strong>
                    </div>
                    <div className="probability-result">
                      <span>Stockout probability</span>
                      <strong>
                        {(prediction.stockout_probability * 100).toFixed(2)}%
                      </strong>
                    </div>
                    <p>Prediction horizon: {prediction.prediction_horizon_days} days</p>
                    <p>Prediction date: {prediction.prediction_date}</p>
                    <p>Model version: {prediction.model_version}</p>
                    <p>Data source: {prediction.data_source}</p>
                    <p>
                      Production ready: {prediction.is_production_ready ? 'Yes' : 'No — demo only'}
                    </p>
                  </div>
                )}
              </div>

              <div className="panel" id="replenishment">
                <div className="panel-heading">
                  <div>
                    <h3>Supplier Replenishment</h3>
                    <p>Calculate order quantity and supplier cost</p>
                  </div>
                  <span className="live-label">● API READY</span>
                </div>

                <form onSubmit={runSupplierRecommendation} className="prediction-form">
                  <div className="selected-product">
                    <span>Selected product</span>
                    <strong>
                      {getProduct(inventory[0]?.product_id ?? '')?.product_name
                        ?? 'No inventory product'}
                    </strong>
                  </div>

                  <div className="prediction-input-grid">
                    <div className="form-field">
                      <label htmlFor="forecast-demand">Forecast demand</label>
                      <input
                        id="forecast-demand"
                        type="number"
                        min="0"
                        step="any"
                        value={forecastDemand}
                        onChange={(e) => setForecastDemand(e.target.value)}
                        required
                      />
                    </div>

                    <div className="form-field">
                      <label htmlFor="safety-stock">Safety stock</label>
                      <input
                        id="safety-stock"
                        type="number"
                        min="0"
                        step="any"
                        value={safetyStock}
                        onChange={(e) => setSafetyStock(e.target.value)}
                        required
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="predict-button"
                    disabled={recommending || inventory.length === 0}
                  >
                    {recommending ? 'Calculating...' : 'Get Supplier Recommendation'}
                  </button>
                </form>

                {replenishmentError && (
                  <div className="error-message">{replenishmentError}</div>
                )}

                {supplierRecommendation && (
                  <div className="prediction-result">
                    <h3>Supplier Recommendation</h3>
                    <div className="risk-result">
                      <span>Recommended order</span>
                      <strong>{supplierRecommendation.recommended_quantity} units</strong>
                    </div>
                    <div className="probability-result">
                      <span>Estimated total cost</span>
                      <strong>
                        {supplierRecommendation.currency} {supplierRecommendation.estimated_total_cost}
                      </strong>
                    </div>
                    <p>Supplier: {supplierRecommendation.supplier_name}</p>
                    <p>Supplier SKU: {supplierRecommendation.supplier_sku ?? '—'}</p>
                    <p>Unit cost: {supplierRecommendation.currency} {supplierRecommendation.unit_cost}</p>
                    <p>Required quantity: {supplierRecommendation.required_quantity}</p>
                    <p>Available inventory: {supplierRecommendation.available_inventory}</p>
                    <p>Confirmed inbound: {supplierRecommendation.confirmed_inbound}</p>
                    <p>Lead time: {supplierRecommendation.lead_time_days} days</p>
                    <p>Minimum order quantity: {supplierRecommendation.minimum_order_quantity}</p>
                    <p>Pack size: {supplierRecommendation.pack_size}</p>
                    <p>Preferred supplier: {supplierRecommendation.is_preferred_supplier ? 'Yes' : 'No'}</p>
                    <button
                      type="button"
                      className="predict-button"
                      onClick={createPurchaseOrder}
                      disabled={poBusyId !== ''}
                    >
                      {poBusyId === 'create' ? 'Creating draft...' : 'Create Draft Purchase Order'}
                    </button>
                  </div>
                )}
              </div>

              <div className="panel" id="purchase-orders">
                <div className="panel-heading">
                  <div>
                    <h3>Purchase Orders</h3>
                    <p>Supplier order management</p>
                  </div>
                </div>
                {poMessage && <p className="live-label">{poMessage}</p>}
                {poError && <div className="error-message">{poError}</div>}

                {purchaseOrders.length === 0 ? (
                  <div className="feature-placeholder">
                    <span>▣</span>
                    <strong>No purchase orders yet</strong>
                    <p>Generate a supplier recommendation to create your first draft order.</p>
                  </div>
                ) : (
                  <div>
                    {purchaseOrders.map((po) => (
                      <div className="prediction-result" key={po.id}>
                        <h3>{po.po_number}</h3>
                        <div className="risk-result">
                          <span>Status</span>
                          <strong>{po.status.replaceAll('_', ' ')}</strong>
                        </div>
                        <div className="probability-result">
                          <span>Order total</span>
                          <strong>{po.currency} {po.total_amount}</strong>
                        </div>
                        <p>Order lines: {po.lines?.length ?? 0}</p>
                        {po.lines?.map((line) => (
                          <p key={line.id}>
                            SKU: {line.supplier_sku ?? '—'} · Ordered: {line.ordered_quantity} · Received: {line.received_quantity}
                          </p>
                        ))}
                        {(po.status === 'SUBMITTED' || po.status === 'PARTIALLY_RECEIVED') &&
                          po.lines?.map((line) => {
                            const outstanding = Number(line.ordered_quantity) - Number(line.received_quantity)
                            if (outstanding <= 0) return null

                            return (
                              <div className="form-field" key={`receive-${line.id}`}>
                                <label htmlFor={`receive-${line.id}`}>
                                  Receive quantity (outstanding: {outstanding})
                                </label>
                                <input
                                  id={`receive-${line.id}`}
                                  type="number"
                                  min="0.001"
                                  max={outstanding}
                                  step="0.001"
                                  value={receiveQuantities[line.id] ?? String(outstanding)}
                                  onChange={(event) => setReceiveQuantities((current) => ({
                                    ...current,
                                    [line.id]: event.target.value,
                                  }))}
                                />
                                <button
                                  type="button"
                                  className="predict-button"
                                  disabled={poBusyId !== ''}
                                  onClick={() => receiveGoods(
                                    po.id,
                                    line.id,
                                    receiveQuantities[line.id] ?? String(outstanding),
                                  )}
                                >
                                  {poBusyId === po.id ? 'Receiving...' : 'Receive Goods'}
                                </button>
                              </div>
                            )
                          })}

                        {po.external_reference && (
                          <p>Mock ERP reference: {po.external_reference}</p>
                        )}

                        {po.status === 'DRAFT' && (
                          <button
                            type="button"
                            className="predict-button"
                            disabled={poBusyId !== ''}
                            onClick={() => runPoAction(po.id, 'approve')}
                          >
                            {poBusyId === po.id ? 'Processing...' : 'Approve Purchase Order'}
                          </button>
                        )}

                        {po.status === 'APPROVED' && (
                          <button
                            type="button"
                            className="predict-button"
                            disabled={poBusyId !== ''}
                            onClick={() => runPoAction(po.id, 'submit')}
                          >
                            {poBusyId === po.id ? 'Submitting...' : 'Submit to Mock ERP'}
                          </button>
                        )}

                        {po.status === 'SUBMITTED' && (
                          <p>Submitted to mock ERP. Awaiting goods receipt.</p>
                        )}
                        {po.status === 'PARTIALLY_RECEIVED' && (
                          <p>Partially received. More goods are expected.</p>
                        )}
                        {po.status === 'RECEIVED' && (
                          <p>Goods received successfully.</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  )
}

export default App

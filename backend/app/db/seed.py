from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import utcnow
from app.db.models import (
    Admin,
    KnowledgeChunk,
    KnowledgeDocument,
    Order,
    OrderItem,
    Product,
    Shipment,
)
from app.db.session import SessionLocal


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ensure_admin(db: Session) -> Admin:
    settings = get_settings()
    email = settings.seed_admin_email.strip().lower()
    admin = db.scalar(select(Admin).where(Admin.email == email))
    if admin is None:
        admin = Admin(
            email=email,
            display_name=settings.seed_admin_name,
            password_hash=hash_password(settings.seed_admin_password),
            is_active=True,
        )
        db.add(admin)
        db.flush()
    return admin


def _ensure_products(db: Session) -> dict[str, Product]:
    product_rows = [
        {
            "sku": "QH-LAMP-001",
            "name": "青禾护眼台灯",
            "category": "居家照明",
            "description": "三档色温、无频闪的桌面护眼灯，适合阅读和夜间办公。",
            "price_cents": 16900,
            "status": "active",
        },
        {
            "sku": "QH-CUP-002",
            "name": "云朵保温杯 480ml",
            "category": "饮水器具",
            "description": "316 不锈钢内胆，轻量杯身与防漏杯盖，适合通勤携带。",
            "price_cents": 8900,
            "status": "active",
        },
        {
            "sku": "QH-BOX-003",
            "name": "原木桌面收纳盒",
            "category": "桌面收纳",
            "description": "榉木材质双层收纳盒，可整理文具、充电线和随身小物。",
            "price_cents": 12900,
            "status": "active",
        },
        {
            "sku": "QH-PILLOW-004",
            "name": "棉麻抱枕套",
            "category": "布艺家纺",
            "description": "可拆洗棉麻抱枕套，适配 45cm × 45cm 枕芯。",
            "price_cents": 5900,
            "status": "active",
        },
        {
            "sku": "QH-CANDLE-005",
            "name": "雨后森林香薰蜡烛",
            "category": "香氛",
            "description": "雪松与苔藓调香型，大豆蜡配方，燃烧时间约 35 小时。",
            "price_cents": 6900,
            "status": "active",
        },
        {
            "sku": "QH-BOTTLE-006",
            "name": "旅行分装瓶套装",
            "category": "旅行用品",
            "description": "含喷雾瓶、按压瓶和收纳袋，符合短途出行携带需求。",
            "price_cents": 3900,
            "status": "active",
        },
    ]

    products: dict[str, Product] = {}
    for row in product_rows:
        product = db.scalar(select(Product).where(Product.sku == row["sku"]))
        if product is None:
            product = Product(**row)
            db.add(product)
            db.flush()
        products[row["sku"]] = product
    return products


def _ensure_orders(db: Session, products: dict[str, Product]) -> int:
    now = utcnow().replace(second=0, microsecond=0)
    order_rows = [
        {
            "order_no": "QH20261021001",
            "customer_name": "林小满",
            "customer_phone": "138****1001",
            "shipping_address": "杭州市西湖区青禾路 18 号 2 幢 301",
            "status": "completed",
            "placed_at": now - timedelta(days=10, hours=2),
            "delivered_at": now - timedelta(days=3),
            "items": [("QH-LAMP-001", 1), ("QH-CANDLE-005", 1)],
            "shipment": (
                "顺丰速运",
                "SF100000000001",
                "delivered",
                "已签收，签收人：本人",
                now - timedelta(days=3),
            ),
        },
        {
            "order_no": "QH20261026002",
            "customer_name": "周予安",
            "customer_phone": "139****2008",
            "shipping_address": "上海市徐汇区梧桐街 27 号 1 单元 702",
            "status": "shipped",
            "placed_at": now - timedelta(days=3, hours=5),
            "delivered_at": None,
            "items": [("QH-CUP-002", 2)],
            "shipment": (
                "中通快递",
                "ZT200000000002",
                "in_transit",
                "快件已到达杭州转运中心",
                None,
            ),
        },
        {
            "order_no": "QH20261028003",
            "customer_name": "陈星河",
            "customer_phone": "137****3021",
            "shipping_address": "南京市鼓楼区云杉路 6 号 4 幢 1201",
            "status": "delivered",
            "placed_at": now - timedelta(days=5, hours=1),
            "delivered_at": now - timedelta(days=1, hours=3),
            "items": [("QH-LAMP-001", 1)],
            "shipment": (
                "顺丰速运",
                "SF300000000003",
                "delivered",
                "已签收，包裹放置于门卫处",
                now - timedelta(days=1, hours=3),
            ),
        },
        {
            "order_no": "QH20261030004",
            "customer_name": "许知夏",
            "customer_phone": "136****4006",
            "shipping_address": "苏州市姑苏区青石巷 11 号 2 单元 503",
            "status": "paid",
            "placed_at": now - timedelta(hours=8),
            "delivered_at": None,
            "items": [("QH-PILLOW-004", 2), ("QH-BOTTLE-006", 1)],
            "shipment": None,
        },
        {
            "order_no": "QH20261011005",
            "customer_name": "顾言川",
            "customer_phone": "135****5012",
            "shipping_address": "宁波市鄞州区月湖路 9 号 3 幢 802",
            "status": "completed",
            "placed_at": now - timedelta(days=20, hours=4),
            "delivered_at": now - timedelta(days=15),
            "items": [("QH-BOX-003", 1)],
            "shipment": (
                "圆通速递",
                "YT500000000005",
                "delivered",
                "已签收，本人签收",
                now - timedelta(days=15),
            ),
        },
        {
            "order_no": "QH20261029006",
            "customer_name": "沈一听",
            "customer_phone": "134****6033",
            "shipping_address": "无锡市滨湖区松风路 32 号 1 单元 1602",
            "status": "shipped",
            "placed_at": now - timedelta(days=2, hours=7),
            "delivered_at": None,
            "items": [("QH-CANDLE-005", 3)],
            "shipment": (
                "韵达快递",
                "YD600000000006",
                "in_transit",
                "已揽收，发往上海分拨中心",
                None,
            ),
        },
        {
            "order_no": "QH20261031007",
            "customer_name": "宋清和",
            "customer_phone": "133****7044",
            "shipping_address": "合肥市蜀山区望江西路 55 号 5 幢 901",
            "status": "paid",
            "placed_at": now - timedelta(hours=2),
            "delivered_at": None,
            "items": [("QH-LAMP-001", 1), ("QH-BOX-003", 1)],
            "shipment": None,
        },
        {
            "order_no": "QH20261025008",
            "customer_name": "陶然",
            "customer_phone": "132****8057",
            "shipping_address": "武汉市洪山区东湖路 102 号 8 幢 601",
            "status": "cancelled",
            "placed_at": now - timedelta(days=6, hours=3),
            "delivered_at": None,
            "items": [("QH-CUP-002", 1)],
            "shipment": None,
        },
    ]

    created = 0
    for row in order_rows:
        existing = db.scalar(select(Order).where(Order.order_no == row["order_no"]))
        if existing is not None:
            continue

        order_items = []
        total_cents = 0
        for sku, quantity in row["items"]:
            product = products[sku]
            total_cents += product.price_cents * quantity
            order_items.append(
                OrderItem(
                    product_id=product.id,
                    sku_snapshot=product.sku,
                    product_name_snapshot=product.name,
                    quantity=quantity,
                    unit_price_cents=product.price_cents,
                )
            )

        order = Order(
            order_no=row["order_no"],
            customer_name=row["customer_name"],
            customer_phone=row["customer_phone"],
            shipping_address=row["shipping_address"],
            status=row["status"],
            total_cents=total_cents,
            placed_at=row["placed_at"],
            delivered_at=row["delivered_at"],
            items=order_items,
        )

        shipment_row = row["shipment"]
        if shipment_row is not None:
            carrier, tracking_no, status, latest_event, delivered_at = shipment_row
            order.shipment = Shipment(
                carrier=carrier,
                tracking_no=tracking_no,
                status=status,
                latest_event=latest_event,
                estimated_delivery_date=(now + timedelta(days=1)).date()
                if status != "delivered"
                else None,
                shipped_at=row["placed_at"] + timedelta(hours=18),
                delivered_at=delivered_at,
            )

        db.add(order)
        created += 1
    return created


def _ensure_knowledge(db: Session) -> int:
    docs = [
        {
            "title": "青禾生活售后政策（2026 版）",
            "doc_type": "policy",
            "version": "2026.1",
            "source_name": "synthetic://policy/after-sales-2026",
            "effective_date": date(2026, 1, 1),
            "chunks": [
                (
                    "七天无理由退货",
                    "消费者签收商品之日起七天内，在商品完好、不影响二次销售的前提下，"
                    "可申请无理由退货。定制商品、已拆封的贴身用品和明确标注不参与"
                    "无理由退货的商品除外。退回运费由消费者承担，质量问题除外。",
                ),
                (
                    "质量问题处理",
                    "商品在签收后十五天内出现非人为损坏、功能故障或明显色差等质量问题，"
                    "可提交照片或视频凭证申请换货或退货。经确认属于质量问题的，"
                    "往返运费由商家承担。",
                ),
                (
                    "退款时效",
                    "退货商品完成签收和质检后，退款将在三个工作日内原路退回。"
                    "银行卡到账时间可能受银行处理时效影响，通常不超过七个工作日。",
                ),
            ],
        },
        {
            "title": "发货与物流说明",
            "doc_type": "logistics",
            "version": "1.2",
            "source_name": "synthetic://logistics/shipping-guide",
            "effective_date": date(2026, 3, 1),
            "chunks": [
                (
                    "发货时效",
                    "现货商品通常在付款后四十八小时内发出。大促期间订单量较大，"
                    "发货时间可能延长至七十二小时，具体以订单详情页展示为准。",
                ),
                (
                    "物流异常",
                    "若物流信息超过四十八小时未更新，或包裹显示异常签收，"
                    "请提供订单号和收件手机号后四位，人工客服将协助联系承运商核查。",
                ),
                (
                    "配送范围",
                    "默认使用顺丰、中通、圆通或韵达发货。偏远地区可能产生额外运费，"
                    "具体配送范围和时效以下单页面提示为准。",
                ),
            ],
        },
        {
            "title": "青禾生活常见问题 FAQ",
            "doc_type": "faq",
            "version": "1.0",
            "source_name": "synthetic://faq/customer-service",
            "effective_date": date(2026, 6, 1),
            "chunks": [
                (
                    "修改收货信息",
                    "订单发货前可以联系人工客服申请修改收货地址或联系电话。"
                    "订单一经发出，地址修改需由承运商确认，不保证一定成功。",
                ),
                (
                    "发票申请",
                    "支持开具电子普通发票。订单完成后可在订单详情页提交抬头和税号，"
                    "发票将在三个工作日内发送至预留邮箱。",
                ),
                (
                    "联系人工客服",
                    "当自助问答无法解决问题、涉及退款争议或需要修改订单时，"
                    "可以申请转人工。人工客服的服务时间为每天九点至二十一点。",
                ),
            ],
        },
    ]

    created = 0
    for doc in docs:
        existing = db.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.title == doc["title"])
        )
        if existing is not None:
            continue

        chunks = []
        for index, (heading, content) in enumerate(doc["chunks"]):
            chunks.append(
                KnowledgeChunk(
                    chunk_index=index,
                    heading=heading,
                    content=content,
                    vector_status="pending",
                    content_hash=_content_hash(content),
                )
            )
        full_text = "\n".join(content for _, content in doc["chunks"])
        db.add(
            KnowledgeDocument(
                title=doc["title"],
                doc_type=doc["doc_type"],
                version=doc["version"],
                status="active",
                source_name=doc["source_name"],
                checksum=_content_hash(full_text),
                effective_date=doc["effective_date"],
                chunks=chunks,
            )
        )
        created += 1
    return created


def seed() -> dict[str, int]:
    with SessionLocal() as db:
        _ensure_admin(db)
        products = _ensure_products(db)
        orders_created = _ensure_orders(db, products)
        knowledge_created = _ensure_knowledge(db)
        db.commit()

        return {
            "products": len(products),
            "orders_created": orders_created,
            "knowledge_documents_created": knowledge_created,
        }


def main() -> None:
    summary = seed()
    print("Seed completed:")
    print(f"  products: {summary['products']}")
    print(f"  orders created: {summary['orders_created']}")
    print(f"  knowledge documents created: {summary['knowledge_documents_created']}")
    print(f"  run at: {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()

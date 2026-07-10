from datetime import timedelta
from decimal import Decimal

from .extensions import db
from .models import Category, Content, Creator, LiveStream, Role, User, Venue, VenueDevice, Wallet, WalletPackage, utcnow


def seed_database() -> None:
    if db.session.scalar(db.select(Role).limit(1)):
        return
    member_role = Role(name="member")
    operator_role = Role(name="operator")
    admin_role = Role(name="admin")
    member = User(email="member@hominsu.local", display_name="VR 여행자", role=member_role)
    member.set_password("member1234")
    operator = User(email="operator@hominsu.local", display_name="현장 운영자", role=operator_role)
    operator.set_password("operator1234")
    admin = User(email="admin@hominsu.local", display_name="서비스 관리자", role=admin_role)
    admin.set_password("admin1234")
    member.wallet = Wallet(points_balance=1500, cash_balance=Decimal("25000.00"))
    operator.wallet = Wallet(points_balance=500, cash_balance=Decimal("0.00"))
    admin.wallet = Wallet(points_balance=0, cash_balance=Decimal("0.00"))

    travel = Category(slug="travel", name="여행", description="한국의 명소를 VR로 여행합니다.", sort_order=1)
    culture = Category(slug="culture", name="문화유산", description="시간을 넘어 만나는 한국 문화유산", sort_order=2)
    nature = Category(slug="nature", name="자연", description="몰입형 자연 체험", sort_order=3)
    creator = Creator(name="호민수 스튜디오", bio="한국의 공간과 이야기를 담는 VR 제작팀")
    guest = Creator(name="서울 XR 랩", bio="도시를 새롭게 기록하는 실감 콘텐츠 팀")
    contents = [
        Content(title="경복궁, 시간을 걷다", description="근정전과 경회루를 해설과 함께 둘러보는 8K VR 투어", media_url="https://media.example.com/gyeongbokgung.m3u8", thumbnail_url="https://media.example.com/gyeongbokgung.jpg", category=culture, creator=creator, points_price=300, cash_price=Decimal("3000.00"), is_featured=True),
        Content(title="제주 오름 일출", description="새벽 바람과 함께 오르는 제주 오름 360도 체험", media_url="https://media.example.com/jeju.m3u8", thumbnail_url="https://media.example.com/jeju.jpg", category=nature, creator=creator, points_price=200, cash_price=Decimal("2000.00"), is_featured=True),
        Content(title="한강 야간 비행", description="드론 시점으로 감상하는 서울의 야경", media_url="https://media.example.com/hanriver.m3u8", thumbnail_url="https://media.example.com/hanriver.jpg", category=travel, creator=guest, points_price=0, cash_price=Decimal("0.00")),
    ]
    live = LiveStream(title="북촌 한옥마을 라이브 워크", stream_url="https://live.example.com/bukchon.m3u8", status="live", starts_at=utcnow() - timedelta(minutes=15), creator=guest)
    packages = [
        WalletPackage(code="POINTS_1000", name="포인트 1,000", price=Decimal("10000.00"), points=1000),
        WalletPackage(code="POINTS_3000", name="포인트 3,000 + 보너스", price=Decimal("30000.00"), points=3000, bonus_points=300),
    ]
    venue = Venue(code="SEOUL-DEMO", name="서울 VR 체험관", address="서울특별시 종로구")
    devices = [
        VenueDevice(device_key="SEOUL-HMD-01", name="VR 헤드셋 1", status="online", app_version="1.0.0", last_seen_at=utcnow(), venue=venue),
        VenueDevice(device_key="SEOUL-HMD-02", name="VR 헤드셋 2", status="offline", app_version="1.0.0", venue=venue),
    ]
    db.session.add_all([member, operator, admin, travel, culture, nature, creator, guest, *contents, live, *packages, venue, *devices])
    db.session.commit()

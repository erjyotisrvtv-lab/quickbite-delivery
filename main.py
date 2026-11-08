import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, BeforeValidator, Field
from sqlalchemy import DateTime, String, UniqueConstraint, create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.environ.get('DATABASE_URL','sqlite:///./data/delivery.db')
ORDERS_URL = os.environ.get('ORDERS_URL','http://127.0.0.1:3002').rstrip('/')
if DATABASE_URL.startswith('sqlite:///'):
    Path(DATABASE_URL[len('sqlite:///'):]).parent.mkdir(parents=True,exist_ok=True)
engine=create_engine(DATABASE_URL,pool_pre_ping=True,pool_size=5,max_overflow=3)
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False)

class Base(DeclarativeBase): pass
class Delivery(Base):
    __tablename__='deliveries'
    __table_args__=(UniqueConstraint('order_id',name='uq_deliveries_order_id'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    order_id:Mapped[str]=mapped_column(String(36),nullable=False)
    customer_address:Mapped[str]=mapped_column(String(300),nullable=False)
    status:Mapped[str]=mapped_column(String(30),default='queued')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

Clean=Annotated[str,BeforeValidator(lambda s:s.strip() if isinstance(s,str) else s)]
class DeliveryRequest(BaseModel):
    orderId:Clean=Field(min_length=1,max_length=80)
    customerAddress:Clean=Field(min_length=1,max_length=300)

def delivery_out(d:Delivery)->dict:
    return {'id':d.id,'orderId':d.order_id,'customerAddress':d.customer_address,
            'status':d.status,'createdAt':d.created_at.isoformat() if d.created_at else None}

@asynccontextmanager
async def lifespan(app:FastAPI):
    for attempt in range(30):
        try:
            Base.metadata.create_all(engine); break
        except OperationalError:
            if attempt==29:raise
            time.sleep(1)
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0),limits=httpx.Limits(max_connections=100,max_keepalive_connections=20)) as client:
        app.state.orders_client=client
        yield
    engine.dispose()

app=FastAPI(title='QuickBite Delivery Service',version='1.0.0',lifespan=lifespan)
@app.get('/health')
def health():
    try:
        with engine.connect() as conn: conn.execute(text('SELECT 1'))
        return {'status':'ok','database':'connected'}
    except Exception as exc:
        raise HTTPException(status_code=503,detail='Delivery database unavailable') from exc

@app.get('/live')
def live(): return {'status':'ok'}

@app.post('/deliveries',status_code=201)
async def create_delivery(delivery:DeliveryRequest):
    try: order_id=str(uuid.UUID(delivery.orderId))
    except ValueError:raise HTTPException(status_code=422,detail='Invalid order ID')
    try: response=await app.state.orders_client.get(f'{ORDERS_URL}/orders/{order_id}')
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503,detail='Orders service unavailable') from exc
    if response.status_code==404:raise HTTPException(status_code=404,detail='Order not found')
    if response.status_code!=200:raise HTTPException(status_code=502,detail='Orders service error')
    entity=Delivery(id=str(uuid.uuid4()),order_id=order_id,customer_address=delivery.customerAddress,
                    status='queued',created_at=datetime.now(timezone.utc))
    try:
        with SessionLocal.begin() as session:session.add(entity)
    except IntegrityError as exc:
        raise HTTPException(status_code=409,detail='A delivery already exists for this order') from exc
    return delivery_out(entity)

@app.get('/deliveries/{delivery_id}')
def get_delivery(delivery_id:str):
    try: delivery_id=str(uuid.UUID(delivery_id))
    except ValueError:raise HTTPException(status_code=404,detail='Delivery not found')
    with SessionLocal() as session:
        entity=session.get(Delivery,delivery_id)
        if entity is None: raise HTTPException(status_code=404,detail='Delivery not found')
        return delivery_out(entity)

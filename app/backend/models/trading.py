from sqlalchemy import Boolean, Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.backend.models.database import Base


class Margin(Base):
    __tablename__ = "margin"

    id = Column(Integer, primary_key=True, index=True)
    margin = Column(Float)
    ticker = Column(String)
    signal = Column(String)
    time = Column(String)


class Buy(Base):
    __tablename__ = "buy"

    id = Column(Integer, primary_key=True, index=True)
    price = Column(Float)
    ticker = Column(String)
    signal = Column(String)
    time = Column(String)


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True)
    figi = Column(String, unique=True)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True)
    ticker = Column(String)
    signal = Column(String)
    bm_value = Column(Float)
    operation_type = Column(String)


class InvestmentPlan(Base):
    __tablename__ = "investment_plans"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    lots = Column(Integer)
    schedule = Column(String)
    time = Column(String)
    price_rule = Column(String)
    order_type = Column(String)
    confirmation_required = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class InvestmentPlanExecution(Base):
    __tablename__ = "investment_plan_executions"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, index=True)
    order_id = Column(String, nullable=True)
    ticker = Column(String, index=True)
    amount_rub = Column(Float, default=0.0)
    status = Column(String, index=True)
    execution_mode = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

from repositories.dashboard_repository import DashboardRepository
from repositories.meta_repository import MetaRepository
from logic.cal_values import calc_order_qty_packs, get_pacsu_by_co, get_produced_qty_packs

class OrderService:
    def __init__(self):
        self.dashboard_repo = DashboardRepository()
        self.meta_repo = MetaRepository()

    def update_all_order_qty(self, sdate_str, product_list):
        """
        모든 제품의 최종 발주량(order_qty_after) 재계산 및 업데이트
        """
        updated_count = 0
        for base_co, vendor in product_list:
            base_co = str(base_co).strip()
            
            # 1. PACSU 조회
            pacsu = get_pacsu_by_co(base_co)
            if pacsu is None or pacsu <= 0:
                pacsu = 1
                
            # 2. 발주 팩 수 계산
            new_qty_packs = int(calc_order_qty_packs(
                base_co=base_co,
                vendor=vendor,
                sdate_str=sdate_str,
                pacsu=pacsu
            ))
            
            # 3. DB 업데이트 (Repository 사용)
            # 기존 로직: UPDATE ORDER_DASHBOARD SET order_qty_after = ...
            # 여기서는 편의상 execute를 바로 쓰거나 repo에 메서드 추가
            # DashboardRepository에 update_order_qty_after_by_co 추가 필요
            # 우선은 직접 repo 메서드 호출하도록 구현
            self.dashboard_repo._execute(
                "UPDATE ORDER_DASHBOARD SET order_qty_after = %s WHERE CONVERT(DATE, sdate) = %s AND co = %s",
                [new_qty_packs, sdate_str, base_co]
            )
            updated_count += 1
            
        return updated_count
